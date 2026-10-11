from flask import Flask, request, jsonify #Import all necessary files
from adafruit_motorkit import MotorKit
import requests

kit = MotorKit(0x40)
app = Flask(__name__) #Create the flask server

@app.route('/', methods=['POST'])  #This function recieves the method from the Computer.
def control():
    try:   #Test whether or not the function was even recieved (debugging purposes)
        command = request.json['command']
    except KeyError:
        return jsonify({'status': 'error', 'message': 'Command not provided'})
    if command == 'forward':
        forward()
    elif command == 'backward':
        backward()
    elif command == 'left':
        left(0.9)
    elif command == 'right':
        right(0.85)
    elif command == 'stop':
        stop()
    else:
        return jsonify({'status': 'error', 'message': 'Invalid command'})

    return jsonify({'status': 'success', 'message': 'Command executed'})

#These just move the motors.
def forward():
  print("Move forward")
  kit.motor1.throttle=-0.8
  kit.motor2.throttle=0.8


def backward():
    print("Move backward")
    kit.motor1.throttle = 0.8
    kit.motor2.throttle = -0.8


def left(time):
    kit.motor1.throttle=0.8
    kit.motor2.throttle=0.8
  

def right(time):
    kit.motor1.throttle=-0.8
    kit.motor2.throttle=-0.8


def stop():
    kit.motor1.throttle = 0.0
    kit.motor2.throttle = 0.0

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
