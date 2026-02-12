import serial
import time

PORT = 'COM3'       # Our port
BAUD = 9600         # Must match the STM32 baud rate
TIMEOUT = 2         # Seconds to wait for a response
message = "Hello :)" 

ser = serial.Serial(port=PORT)

while True:
    ser.write((message).encode('utf-8'))
    print("Message sent successfully\n")
    print("Waiting for response...\n")
    response = ser.readline()
