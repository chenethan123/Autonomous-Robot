"""Lane overlay: traces the outer lines of the current lane in a driving video and
draws the estimated center path between them.

Pipeline per frame:
  1. Color/gradient threshold (white + yellow paint, strong vertical edges).
  2. Region-of-interest mask so walls, sky, signs and other cars are ignored.
  3. Canny + HoughLinesP on the masked edges, filtered by slope/side, to get a
     rough straight-line estimate of the left and right lane lines.
  4. Perspective transform to a bird's-eye view, then a sliding-window search
     (seeded by the Hough lines) that fits a 2nd-order curve to each line.
  5. Temporal smoothing, then the lane, its outer lines and the center line are
     projected back onto the original frame.

Usage:
  python lane_overlay.py input.mp4
  python lane_overlay.py input.mp4 --output out.mp4 --no-display

Keys while playing: q/Esc quit, space pause, d toggle debug view.
"""
import argparse
import sys
import time
from collections import deque

import cv2 as cv
import numpy as np

# Frames are resized to this width before processing so the pixel thresholds
# below behave the same regardless of the source resolution.
PROC_WIDTH = 960

# Where the road vanishes on the horizon, as fractions of (width, height). The
# region of interest and the perspective transform are both built from it. It is
# re-estimated from the first stretch of video unless --no-calibrate is passed.
DEFAULT_VANISHING_POINT = (0.50, 0.60)
CALIBRATION_FRAMES = 30

# Perspective source trapezoid: bottom edge height and half-width (fractions of
# the frame), and how far up toward the vanishing point the top edge sits.
SRC_BOTTOM = 0.95
SRC_HALF_WIDTH = 0.38
SRC_REACH = 0.85

# Where the source trapezoid lands in the bird's-eye image.
DST = np.float32([[0.25, 1.00], [0.25, 0.00], [0.75, 0.00], [0.75, 1.00]])

# Real-world scale assumptions for the readouts (US lane width, ~30m look-ahead).
LANE_WIDTH_M = 3.7
LOOKAHEAD_M = 30.0

LEFT_COLOR = (0, 0, 255)
RIGHT_COLOR = (255, 0, 0)
CENTER_COLOR = (0, 255, 255)
LANE_FILL = (0, 180, 0)


def scale(points, w, h):
    return np.float32(points * np.float32([w, h]))


def poly_x(fit, y):
    return fit[0] * y ** 2 + fit[1] * y + fit[2]


def lane_pixels(frame):
    """Binary mask of pixels that look like lane paint."""
    hls = cv.cvtColor(frame, cv.COLOR_BGR2HLS)
    lightness = hls[:, :, 1]
    white = cv.inRange(hls, (0, 190, 0), (180, 255, 255))
    yellow = cv.inRange(hls, (15, 70, 80), (40, 230, 255))  # OpenCV hue is 0-180

    sobel = np.abs(cv.Sobel(lightness, cv.CV_32F, 1, 0, ksize=3))
    sobel = np.uint8(255 * sobel / max(float(sobel.max()), 1.0))
    # Strong horizontal gradients catch faded paint, but only on fairly bright
    # pixels; dark gradients are usually car bumpers, shadows and tar seams.
    grad = cv.inRange(sobel, 50, 255) & cv.inRange(lightness, 120, 255)
    return white | yellow, grad


class LaneTracker:
    """Smooths per-frame fits and fills in a side that drops out briefly."""

    def __init__(self, width, history=8, max_missed=20):
        self.width = width
        self.max_missed = max_missed
        self.fits = {"left": deque(maxlen=history), "right": deque(maxlen=history)}
        self.missed = {"left": 0, "right": 0}
        self.lane_width = None  # in bird's-eye pixels, measured at the bottom

    def best(self, side):
        fits = self.fits[side]
        return np.mean(fits, axis=0) if fits else None

    def update(self, side, fit, y_eval):
        prev = self.best(side)
        # Reject sudden jumps (a car or crack grabbed the window) unless the
        # line has been lost long enough that we should trust the new one.
        if fit is not None and prev is not None and self.missed[side] < 5:
            if abs(poly_x(fit, y_eval) - poly_x(prev, y_eval)) > 0.08 * self.width:
                fit = None
        if fit is None:
            self.missed[side] += 1
            if self.missed[side] > self.max_missed:
                self.fits[side].clear()
        else:
            self.missed[side] = 0
            self.fits[side].append(fit)

    def lanes(self, y_eval):
        left, right = self.best("left"), self.best("right")
        if left is not None and right is not None:
            measured = poly_x(right, y_eval) - poly_x(left, y_eval)
            self.lane_width = measured if self.lane_width is None else 0.9 * self.lane_width + 0.1 * measured
        # Only one side visible: estimate the other one a lane-width away.
        elif self.lane_width is not None:
            if left is not None:
                right = left + np.array([0, 0, self.lane_width])
            elif right is not None:
                left = right - np.array([0, 0, self.lane_width])
        return left, right

    def reset(self):
        for side in self.fits:
            self.fits[side].clear()
            self.missed[side] = 0
        self.lane_width = None


class LaneDetector:
    def __init__(self, w, h, calibrate=True):
        self.w, self.h = w, h
        self.dst = scale(DST, w, h)
        self.expected_width = self.dst[3][0] - self.dst[0][0]
        self.tracker = LaneTracker(w)
        self.vp_samples = [] if calibrate else None
        self.set_vanishing_point(DEFAULT_VANISHING_POINT[0] * w, DEFAULT_VANISHING_POINT[1] * h)

    def set_vanishing_point(self, vx, vy):
        """Builds the ROI and perspective transform from the vanishing point, so
        the trapezoid sides follow the road's own perspective lines."""
        w, h = self.w, self.h
        self.vp = (vx, vy)

        def toward_vp(x, y, t):
            return [x + (vx - x) * t, y + (vy - y) * t]

        bottom = SRC_BOTTOM * h
        bl, br = [vx - SRC_HALF_WIDTH * w, bottom], [vx + SRC_HALF_WIDTH * w, bottom]
        self.src = np.float32([bl, toward_vp(*bl, SRC_REACH), toward_vp(*br, SRC_REACH), br])
        self.M = cv.getPerspectiveTransform(self.src, self.dst)
        self.Minv = cv.getPerspectiveTransform(self.dst, self.src)

        # ROI: a wider wedge under the vanishing point, stopping just below the
        # horizon so the sky, ceiling lights and overhead signs are cut off.
        top = vy + 0.04 * h
        self.roi = np.int32([[vx - 0.75 * w, h], [vx - 0.06 * w, top], [vx + 0.06 * w, top], [vx + 0.75 * w, h]])
        self.roi_mask = np.zeros((h, w), np.uint8)
        cv.fillPoly(self.roi_mask, [self.roi], 255)
        self.tracker.reset()

    def calibrate(self, hough_fits):
        """Collects intersections of the left/right Hough lines and, once there
        are enough, moves the vanishing point to their median."""
        left, right = hough_fits["left"], hough_fits["right"]
        if left is None or right is None or left[0] == right[0]:
            return
        # Both lines are x = m*y + b.
        y = (right[1] - left[1]) / (left[0] - right[0])
        x = left[0] * y + left[1]
        if 0.2 * self.w < x < 0.8 * self.w and 0.25 * self.h < y < 0.8 * self.h:
            self.vp_samples.append((x, y))
        if len(self.vp_samples) >= CALIBRATION_FRAMES:
            self.set_vanishing_point(*np.median(self.vp_samples, axis=0))
            self.vp_samples = None

    # Hough stage (straight-line estimate, also acts as an obstacle filter)
    def hough_lines(self, color_mask):
        gray_blur = cv.GaussianBlur(cv.cvtColor(self.frame, cv.COLOR_BGR2GRAY), (5, 5), 0)
        edges = cv.Canny(gray_blur, 50, 150)
        # Keep only edges that are on lane-colored paint inside the ROI, which
        # drops most car outlines, guard rails and shadows.
        edges &= cv.dilate(color_mask, np.ones((5, 5), np.uint8)) & self.roi_mask

        segments = cv.HoughLinesP(edges, 1, np.pi / 180, threshold=25,
                                  minLineLength=self.h // 25, maxLineGap=self.h // 8)
        groups = {"left": [], "right": []}
        if segments is None:
            return {"left": None, "right": None}, groups

        for x1, y1, x2, y2 in segments.reshape(-1, 4):
            if x1 == x2:
                continue
            slope = (y2 - y1) / (x2 - x1)
            # Near-horizontal segments are crosswalks, shadows, car bumpers etc.
            if not 0.4 < abs(slope) < 5:
                continue
            if slope < 0 and max(x1, x2) < self.vp[0] + 0.1 * self.w:
                groups["left"].append((x1, y1, x2, y2))
            elif slope > 0 and min(x1, x2) > self.vp[0] - 0.1 * self.w:
                groups["right"].append((x1, y1, x2, y2))

        fits = {}
        for side, segs in groups.items():
            if not segs:
                fits[side] = None
                continue
            segs = np.array(segs, np.float32)
            ys = np.concatenate([segs[:, 1], segs[:, 3]])
            xs = np.concatenate([segs[:, 0], segs[:, 2]])
            lengths = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
            # x as a function of y, so steep lines don't blow up.
            fits[side] = np.polyfit(ys, xs, 1, w=np.concatenate([lengths, lengths]))
        return fits, groups

    def to_birdseye_x(self, x, y):
        pt = cv.perspectiveTransform(np.float32([[[x, y]]]), self.M)
        return float(pt[0, 0, 0])

    # Bird's-eye stage (curve fit)
    def find_line(self, nz_x, nz_y, base_x, prev_fit, debug):
        margin = int(self.w * 0.06)
        if prev_fit is not None:
            # Search a band around last frame's curve.
            idx = np.flatnonzero(np.abs(nz_x - poly_x(prev_fit, nz_y)) < margin)
            if debug is not None:
                ys = np.linspace(0, self.h - 1, 30)
                for off in (-margin, margin):
                    pts = np.int32(np.column_stack([poly_x(prev_fit, ys) + off, ys]))
                    cv.polylines(debug, [pts], False, (0, 255, 0), 1)
        else:
            if base_x is None:
                return None
            n_windows = 9
            win_h = self.h // n_windows
            x = int(base_x)
            hits = []
            for i in range(n_windows):
                y_hi = self.h - i * win_h
                y_lo = y_hi - win_h
                good = np.flatnonzero((nz_y >= y_lo) & (nz_y < y_hi) &
                                      (nz_x >= x - margin) & (nz_x < x + margin))
                hits.append(good)
                if debug is not None:
                    cv.rectangle(debug, (x - margin, y_lo), (x + margin, y_hi), (0, 255, 0), 1)
                if len(good) > 40:
                    x = int(nz_x[good].mean())
            idx = np.concatenate(hits)

        if len(idx) < 150:
            return None
        ys = nz_y[idx]
        # Need the paint to span a decent part of the view, otherwise the
        # quadratic term extrapolates wildly.
        if ys.max() - ys.min() < self.h * 0.3:
            return None
        if debug is not None:
            debug[ys, nz_x[idx]] = (0, 0, 255)
        return np.polyfit(ys, nz_x[idx], 2)

    def sane(self, left, right):
        ys = np.array([0, self.h / 2, self.h - 1])
        widths = poly_x(right, ys) - poly_x(left, ys)
        return (widths.min() > 0.6 * self.expected_width and
                widths.max() < 1.5 * self.expected_width and
                widths.max() - widths.min() < 0.35 * self.expected_width)

    def process(self, frame, debug=False):
        self.frame = frame
        color_mask, grad_mask = lane_pixels(frame)
        hough_fits, hough_segments = self.hough_lines(color_mask)
        if self.vp_samples is not None:
            self.calibrate(hough_fits)

        binary = (color_mask | grad_mask) & self.roi_mask
        warped = cv.warpPerspective(binary, self.M, (self.w, self.h), flags=cv.INTER_NEAREST)
        nz_y, nz_x = warped.nonzero()
        dbg = cv.cvtColor(warped, cv.COLOR_GRAY2BGR) if debug else None

        # Window start points: prefer the Hough lines, fall back to a histogram.
        bottom = self.h - 1
        hist = np.sum(warped[self.h // 2:, :], axis=0)
        mid = self.w // 2
        bases = {}
        for side, (lo, hi) in (("left", (0, mid)), ("right", (mid, self.w))):
            line = hough_fits[side]
            x = self.to_birdseye_x(np.polyval(line, bottom), bottom) if line is not None else None
            if x is None or not lo <= x < hi:
                x = lo + int(np.argmax(hist[lo:hi])) if hist[lo:hi].max() > 0 else None
            bases[side] = x

        fits = {side: self.find_line(nz_x, nz_y, bases[side], self.tracker.best(side), dbg)
                for side in ("left", "right")}
        if fits["left"] is not None and fits["right"] is not None and not self.sane(fits["left"], fits["right"]):
            fits = {"left": None, "right": None}
        for side, fit in fits.items():
            self.tracker.update(side, fit, bottom)
        left, right = self.tracker.lanes(bottom)

        out = self.draw(frame, left, right)
        if debug:
            cv.polylines(out, [self.roi], True, (255, 0, 255), 1)
            cv.polylines(out, [self.src.astype(np.int32)], True, (0, 255, 255), 1)
            for side, segs in hough_segments.items():
                for x1, y1, x2, y2 in segs:
                    cv.line(out, (x1, y1), (x2, y2), (255, 0, 255), 2)
            for fit in (left, right):
                if fit is not None:
                    ys = np.linspace(0, self.h - 1, 30)
                    cv.polylines(dbg, [np.int32(np.column_stack([poly_x(fit, ys), ys]))], False, (0, 255, 255), 2)
            inset_w = self.w // 3
            inset = cv.resize(dbg, (inset_w, inset_w * self.h // self.w))
            out[10:10 + inset.shape[0], self.w - inset_w - 10:self.w - 10] = inset
        return out

    def unwarp(self, xs, ys):
        pts = np.float32(np.column_stack([xs, ys])).reshape(-1, 1, 2)
        return cv.perspectiveTransform(pts, self.Minv).reshape(-1, 2)

    def draw(self, frame, left, right):
        out = frame.copy()
        if left is None or right is None:
            cv.putText(out, "Searching for lane...", (20, 40), cv.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            return out

        ys = np.linspace(0, self.h - 1, 40)
        lx, rx = poly_x(left, ys), poly_x(right, ys)
        cx = (lx + rx) / 2
        left_pts = self.unwarp(lx, ys).astype(np.int32)
        right_pts = self.unwarp(rx, ys).astype(np.int32)
        center_pts = self.unwarp(cx, ys).astype(np.int32)

        overlay = out.copy()
        cv.fillPoly(overlay, [np.vstack([left_pts, right_pts[::-1]])], LANE_FILL)
        out = cv.addWeighted(overlay, 0.3, out, 0.7, 0)

        cv.polylines(out, [left_pts], False, LEFT_COLOR, 6, cv.LINE_AA)
        cv.polylines(out, [right_pts], False, RIGHT_COLOR, 6, cv.LINE_AA)
        # Dashed center line: draw every other segment.
        for i in range(0, len(center_pts) - 1, 2):
            cv.line(out, tuple(center_pts[i]), tuple(center_pts[i + 1]), CENTER_COLOR, 4, cv.LINE_AA)
        cv.arrowedLine(out, tuple(center_pts[8]), tuple(center_pts[0]), CENTER_COLOR, 3, cv.LINE_AA, tipLength=0.3)

        # Readouts: curve radius and how far the car is from the lane center.
        lane_px = rx[-1] - lx[-1]
        xm = LANE_WIDTH_M / lane_px
        ym = LOOKAHEAD_M / self.h
        cfit = np.polyfit(ys * ym, cx * xm, 2)
        y_m = (self.h - 1) * ym
        curvature = 2 * cfit[0]
        radius = (1 + (2 * cfit[0] * y_m + cfit[1]) ** 2) ** 1.5 / abs(curvature) if curvature else float("inf")
        offset = (self.w / 2 - cx[-1]) * xm
        turn = "straight" if radius > 1500 else ("curving left" if curvature < 0 else "curving right")
        side = "right" if offset > 0 else "left"
        radius_text = f"{radius:,.0f} m" if radius < 10000 else "-"
        lines = [f"Curve radius: {radius_text} ({turn})",
                 f"Offset from center: {abs(offset):.2f} m {side}"]
        for i, text in enumerate(lines):
            cv.putText(out, text, (20, 40 + 32 * i), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv.LINE_AA)
            cv.putText(out, text, (20, 40 + 32 * i), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv.LINE_AA)
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", nargs="?", default="input.mp4", help="path to the driving video")
    parser.add_argument("--output", help="write the annotated video to this file (e.g. out.mp4)")
    parser.add_argument("--no-display", action="store_true", help="don't open a window")
    parser.add_argument("--debug", action="store_true", help="start with the debug view on")
    parser.add_argument("--no-calibrate", action="store_true",
                        help="use DEFAULT_VANISHING_POINT instead of estimating it from the video")
    parser.add_argument("--loop", action="store_true", help="restart the video when it ends")
    args = parser.parse_args()

    cap = cv.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"Could not open video: {args.video}")
    fps = cap.get(cv.CAP_PROP_FPS) or 30

    detector = writer = None
    debug, paused = args.debug, False
    frame_time = 1.0
    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                if args.loop and detector is not None:
                    cap.set(cv.CAP_PROP_POS_FRAMES, 0)
                    detector.tracker.reset()
                    continue
                break
            h, w = frame.shape[:2]
            frame = cv.resize(frame, (PROC_WIDTH, round(h * PROC_WIDTH / w)))
            if detector is None:
                detector = LaneDetector(frame.shape[1], frame.shape[0], calibrate=not args.no_calibrate)

            start = time.perf_counter()
            out = detector.process(frame, debug)
            frame_time = 0.9 * frame_time + 0.1 * (time.perf_counter() - start)
            cv.putText(out, f"{1 / frame_time:.0f} fps", (20, out.shape[0] - 20),
                       cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv.LINE_AA)

            if args.output:
                if writer is None:
                    writer = cv.VideoWriter(args.output, cv.VideoWriter_fourcc(*"mp4v"), fps,
                                            (out.shape[1], out.shape[0]))
                writer.write(out)

        if not args.no_display:
            cv.imshow("Lane Overlay", out)
            key = cv.waitKey(max(1, int(1000 / fps)) if not paused else 30) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                paused = not paused
            elif key == ord("d"):
                debug = not debug

    cap.release()
    if writer is not None:
        writer.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()
