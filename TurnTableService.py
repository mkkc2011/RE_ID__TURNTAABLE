import RPi.GPIO as GPIO
import time
import datetime
import logging  
import json
from threading import Thread
import subprocess
import zmq

# Topics 
# =================
# Status :
#          connected
#          not_connected  
#          idle  
#          started
#          processing
#          completed
#          error

# Data : 
#       json dump string

logging.basicConfig(level=logging.DEBUG)

pub_context = zmq.Context()
sub_context = zmq.Context()
publisher = None
subscriber = None 
flagProcessing=0 
 
GPIO.cleanup() 

# Define the GPIO pins for Pulse (PUL) and Direction (DIR)
PUL_PIN = 18  # Replace with the actual GPIO pin numbers you're using
DIR_PIN = 19

# Set the GPIO pin for the buzzer
Motor_ena_pin = 23

# Define the GPIO pin to which the Hall Effect sensor is connected
hall_effect_pin = 6  # Replace with the actual GPIO pin number

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PUL_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN, GPIO.OUT)
# Set the buzzer pin as an output
GPIO.setup(Motor_ena_pin, GPIO.OUT)
GPIO.output(Motor_ena_pin, GPIO.LOW)

# angle init
current_angle = 0

def get_angle(angle_input):
  global current_angle
  current_angle = (current_angle + angle_input) % 360
  return (current_angle + 360) % 360  # Ensure positive value


def control_stepper(delay, steps, clockwise=True):
        # Set the direction (clockwise or counterclockwise)
        if clockwise:
            GPIO.output(DIR_PIN, GPIO.LOW)
        else:
            GPIO.output(DIR_PIN, GPIO.HIGH)
        # Generate step pulses
        for _ in range(steps):
            GPIO.output(PUL_PIN, GPIO.LOW)
            time.sleep(delay)
            GPIO.output(PUL_PIN, GPIO.HIGH)
            time.sleep(delay)


def home():
    # Function to control the stepper motor
    def control_stepper(delay, steps, clockwise=True):
        # Set the direction (clockwise or counterclockwise)
        if clockwise:
            GPIO.output(DIR_PIN, GPIO.LOW)
        else:
            GPIO.output(DIR_PIN, GPIO.HIGH)
        # Generate step pulses
        for _ in range(steps):
            GPIO.output(PUL_PIN, GPIO.LOW)
            time.sleep(delay)
            GPIO.output(PUL_PIN, GPIO.HIGH)
            time.sleep(delay)


    #Initial Push away from the current position: Just a random 90 degree forward move
    control_stepper(.0005, 90, clockwise=False)
    for i in range(1,5):
        # Read the state of the Hall Effect sensor (HIGH or LOW)
        control_stepper(.0005, 12800, clockwise=False)
        sensor_state = GPIO.input(hall_effect_pin)

        if sensor_state == GPIO.HIGH:
            print("Magnetic field detected!")
            break
    # Correction of 15 degree forward to compensate for the long magnet premature detection
    control_stepper(.0005, 15, clockwise=False)

def rotate(Angle):
# Angle = 36000
    Steps_per_Revolution = 12800 #previous = 400
    # delay = 0.0005  # Delay between steps (adjust for your motor and application)

    Degree_per_Step = 360/Steps_per_Revolution

    print("Angle = {}".format(Angle))
    print("....................")
    print()
    print("Degree per Step = {} ".format(Degree_per_Step))

    # Define motor parameters
    steps = int(abs(Angle)*(Steps_per_Revolution/360)) # Number of steps per revolution for your motor
    delay = 0.00035     # Delay between steps (adjust for your motor and application)                 prev deLay= 0.00048
    print("Number of Steps = {}".format(steps))

    # Function to move the motor a specified number of steps in a direction
    def move_motor(direction, steps):
        GPIO.output(DIR_PIN, direction)  # Set the direction (HIGH for forward, LOW for backward)
        for _ in range(steps):
            GPIO.output(PUL_PIN, GPIO.HIGH)
            time.sleep(delay)
            GPIO.output(PUL_PIN, GPIO.LOW)
            time.sleep(delay)
            

    try:
        # Example: Rotate the motor 200 steps clockwise
        if Angle>0:
            move_motor(GPIO.LOW, steps)
        else:
            move_motor(GPIO.HIGH, steps)
        

    except KeyboardInterrupt:
        pass  # Handle keyboard interrupt
# 
    finally:
        #GPIO.cleanup()  # Clean up GPIO pins on program exit
        print("Rotation done with angle {}".format(Angle))

  
def listening_events(): 
    global publisher,subscriber,flagProcessing
     
    while True:
        strResponse = subscriber.recv_string()
        jsonMessage = json.loads(strResponse) 
        print("Received Message ",jsonMessage)

        action=jsonMessage["action"] 
        angle=jsonMessage["angle"] 

        current_timestamp =  datetime.datetime.now().timestamp()
        if(flagProcessing==0):
            if(action=="turn"):
                    flagProcessing=1             
                    jsonData = json.dumps({"status":"started", "timestamp" : current_timestamp}) 
                    publisher.send_string(jsonData)

                    rotate(angle)
                    #print(get_angle(angle))
    
                    jsonData = json.dumps({"status":"completed", "timestamp" : current_timestamp, "angle": angle}) 
                    publisher.send_string(jsonData)
                    flagProcessing=0
                
                    
        if(flagProcessing==1):
                jsonData = json.dumps({"status":"processing", "timestamp" : current_timestamp}) 
                publisher.send_string(jsonData)
                

def send_status():
    global flagProcessing,publisher,subscriber

    while True: 
        current_timestamp =  datetime.datetime.now().timestamp()

        if(flagProcessing==0):    
            jsonData = json.dumps({"status":"idle", "timestamp" : current_timestamp}) 
            publisher.send_string(jsonData)   
            
            time.sleep(1)

        else:              
            jsonData = json.dumps({"status":"processing", "timestamp" : current_timestamp}) 
            publisher.send_string(jsonData)     
            
            time.sleep(1)

def main():
    global flagProcessing,publisher,subscriber

    client_publisher_ip   = "192.168.1.210" # 
    client_publisher_port = 9944  #  
    turntable_publisher_port = 9954  # 

    publisher = pub_context.socket(zmq.PUB)
    publisher.bind("tcp://*:%s" % turntable_publisher_port)
    time.sleep(1)
    
    subscriber = sub_context.socket(zmq.SUB)
    subscriber.connect("tcp://%s:%s" % (client_publisher_ip,client_publisher_port))
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
    time.sleep(1)
    
    thSendStatus = Thread(target=send_status)
    thSendStatus.start()

    thListener = Thread(target=listening_events)
    thListener.start()     

    thListener.join() 
    thSendStatus.join() 
    


if __name__ == "__main__":

    # move to home position 
    #home()

    main()
    GPIO.cleanup() 