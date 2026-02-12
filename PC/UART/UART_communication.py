import serial
import time

PORT = 'COM3'       # Our port
BAUD = 9600         # Must match the STM32 baud rate
TIMEOUT = 2         # Seconds to wait for a response

def send():
    try:
        # Open the connection
        with serial.Serial(PORT, BAUD, timeout=TIMEOUT) as ser:
            print(f"[PC] Connected to {PORT}")
            
            # Wait for board to reset/stabilize
            time.sleep(2) 
            
            # 1. Clear any old data in the buffer
            ser.reset_input_buffer()

            # 2. Transmit the message
            message = "Hello"
            # We add a newline (\n) because many microcontrollers use it to detect end of string
            ser.write((message + "\n").encode('utf-8'))
            print(f"[PC] Sent: {message}")

            # 3. Listen for the confirmation (The "Check")
            print("[PC] Waiting for acknowledgment...")
            response = ser.readline().decode('utf-8').strip()

    except serial.SerialException as e:
        print(f"Error: Could not open port {PORT}. Is it correct?")

if __name__ == "__main__":
    send()