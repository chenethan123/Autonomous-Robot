# python3
import tkinter as tk
from tkinter.ttk import *
from tkinter import *
import requests
from login import extrauser
import cv2 as cv
from PIL import Image, ImageTk
from lane_overlay import LaneDetector, PROC_WIDTH

VIDEO_PATH = 'input.mp4'
LANE_DISPLAY_SIZE = (480, 270)
RAW_DISPLAY_SIZE = (200, 113)

video = cv.VideoCapture(VIDEO_PATH)

from datetime import datetime


fen = tk.Tk()

def update_log_text():
    with open(f"{extrauser}.txt", "r") as file:
        log_content = file.read()
        log_text.config(state=tk.NORMAL)
        log_text.delete("1.0", tk.END)
        log_text.insert(tk.END, log_content)
        log_text.config(state=tk.DISABLED)
        log_text.yview(tk.END)  # scroll down to end!


def show_frame(label, frame, size):
    # converts an OpenCV frame into a tkinter image and puts it on the label
    frame = cv.resize(frame, size)
    opencv_image = cv.cvtColor(frame, cv.COLOR_BGR2RGBA)
    photo_image = ImageTk.PhotoImage(image=Image.fromarray(opencv_image))
    label.photo_image = photo_image
    label.configure(image=photo_image)


def movement(direction):
    time = datetime.now()
    current_hour = time.strftime("%H")
    hourint = int(current_hour) - 5
    if hourint < 0:
        hourint = 24 + hourint
    current_time = time.strftime(f"%Y-%m-%d {hourint}:%M:%S %Z%z")

    with open(f'{extrauser}.txt', 'at') as f:
        f.write(f"{extrauser} pressed {direction} at " + current_time + "\n")

    url = "http://192.168.1.36:5000"
    requests.post(url, json={'command': direction})
    
    update_log_text()


def logout():
    fen.destroy()
    time = datetime.now()
    current_hour = time.strftime("%H")
    hourint = int(current_hour) - 5
    if hourint < 0:
        hourint = 24 + hourint
    current_time = time.strftime(f"%Y-%m-%d {hourint}:%M:%S %Z%z")

    with open(f'{extrauser}.txt', 'at') as f:
        f.write(f"{extrauser} has logged out at " + current_time + "\n")

    update_log_text()




# Create a label widget to display the video feed
label_widget = tk.Label(fen)
label_widget.grid(row=1)

# Create a frame for the video feed
left = tk.Frame(fen, bg="grey", width=500, height=300)
left.pack_propagate(False)
tk.Label(left, text="Line Detection", fg="white", bg="black", anchor="center", justify="center").pack()
left.grid(column=0, row=0, pady=5, padx=10, sticky="n")

# Create a label widget to display the video feed inside the left frame
video_label = tk.Label(left)
video_label.pack()

# lane detection (see lane_overlay.py for the full pipeline)
cap = cv.VideoCapture(VIDEO_PATH)
frame_delay = int(1000 / (cap.get(cv.CAP_PROP_FPS) or 30))
detector = None


def update_video_feed():
    global detector
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        frame = cv.resize(frame, (PROC_WIDTH, round(h * PROC_WIDTH / w)))
        if detector is None:
            detector = LaneDetector(frame.shape[1], frame.shape[0])
        # traces the outer lane lines and draws the estimated center line
        frame = detector.process(frame)
        show_frame(video_label, frame, LANE_DISPLAY_SIZE)
    else:
        # restart the video when it ends
        cap.set(cv.CAP_PROP_POS_FRAMES, 0)
        if detector is not None:
            detector.tracker.reset()

    fen.after(frame_delay, update_video_feed)

update_video_feed()
sty = Style(fen)
sty.configure("TSeparator", background="black")

# TOP RIGHT

right = tk.Frame(fen, width=200, height=200, bg="grey")
right.pack_propagate(False)
tk.Label(right, text="Movement Controls", fg="white", bg="black").pack()
right.grid(column=2, row=0, pady=5, padx=10, sticky="n")

forwardbutton = Button(right, text="↑", width=7, command=lambda: movement("forward"))
forwardbutton.grid(row=0, column=2, pady=(30, 3), padx=10, columnspan=2)

leftbutton = Button(right, text="←", width=3, command=lambda: movement("left"))
leftbutton.grid(row=1, column=1, pady=3)

stopbutton = Button(right, text="◉", width=3, command=lambda: movement("stop"))
stopbutton.grid(row=1, column=2, pady=3)

demobutton = Button(right, text="▶", width=3, command=lambda: movement("demo"))
demobutton.grid(row=1, column=3, pady=3)

rightbutton = Button(right, text="→", width=3, command=lambda: movement("right"))
rightbutton.grid(row=1, column=4, pady=3)

backbutton = Button(right, text="↓", width=7, command=lambda: movement("backward"))
backbutton.grid(row=2, column=2, pady=3, columnspan=2)

logoutbutton = Button(right, text="Logout", width=5, command=lambda: logout())
logoutbutton.grid(row=3, column=2, pady=(20, 16), columnspan=2)

# Bottom Left

bleft = tk.Frame(fen, bg="grey", width=200, height=200)

bleft.pack_propagate(False)
tk.Label(bleft, text="Raw Video", fg="white", bg="black", anchor="center", justify="center").pack()
bleft.grid(column=0, row=1, pady=5, padx=10, sticky="n")
sep = Separator(fen, orient="vertical")
sep.grid(column=1, row=1, sticky="ns")

label_widget = Label(bleft)
label_widget.pack()

def open_cam():
    ret, frame = video.read()
    if ret:
        show_frame(label_widget, frame, RAW_DISPLAY_SIZE)
    else:
        video.set(cv.CAP_PROP_POS_FRAMES, 0)
    label_widget.after(frame_delay, open_cam)

open_cam()

# BOTTOM RIGHT
bright = tk.Frame(fen, bg="grey", width=200, height=200)
bright.pack_propagate(False)
tk.Label(bright, text="Log", fg="white", bg="black").pack()
log_text = tk.Text(bright, fg="white", bg="black", height=10, width=30, wrap=tk.WORD, state=tk.DISABLED)
log_text.grid(column=0, row=2, pady=22, padx=10, sticky="n", rowspan=2)

scrollbar = tk.Scrollbar(bright, command=log_text.yview)

log_text.config(yscrollcommand=scrollbar.set)

bright.grid(column=2, row=1, pady=5, padx=10, sticky="n")

update_log_text()

fen.mainloop()
