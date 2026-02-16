import serial
import time

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'  # Change this to your STM32 Port (e.g., /dev/ttyUSB0 on Linux)
BAUD_RATE = 115200

def test_level_generation():
    try:
        # 1. Open Serial Connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
        
        # 2. Construct Command
        # CMD = 0x01 (Start)
        # DATA = 0x00 (Dummy)
        # CRC = 0x01 ^ 0x00 = 0x01
        cmd_packet = bytes([0x01, 0x00, 0x01])
        
        print(f"Sending: {cmd_packet.hex(' ')}")
        ser.write(cmd_packet)
        
        # 3. Read Response (Expect 52 bytes)
        # 1 Byte CMD + 50 Bytes Data + 1 Byte CRC
        response = ser.read(52)
        
        if len(response) != 52:
            print(f"Error: Received {len(response)} bytes. Expected 52.")
            print(f"Raw rx: {response.hex(' ')}")
            return

        # 4. Parse Response
        rx_cmd = response[0]
        rx_data = response[1:51]
        rx_crc = response[51]
        
        print("\n--- RESPONSE RECEIVED ---")
        print(f"Command Echo: 0x{rx_cmd:02X} (Expected 0x01)")
        print(f"CRC Byte:     0x{rx_crc:02X}")
        
        print("\n--- GENERATED TILES ---")
        groups = ["Bamboo", "Chars", "Circles", "Winds", "Dragons", "Flowers", "Seasons"]
        
        for i, byte in enumerate(rx_data):
            # Unpack the byte
            group_id = (byte >> 5) & 0x07
            value = byte & 0x1F
            
            # Determine Layer
            layer = "L1 (5x5)"
            if i >= 25: layer = "L2 (4x4)"
            if i >= 41: layer = "L3 (3x3)"
            
            group_name = groups[group_id] if group_id < 7 else "Unknown"
            print(f"Tile {i:02d} [{layer}]: {group_name} {value} (Raw: 0x{byte:02X})")

        ser.close()
        print("\nTest Passed!")

    except serial.SerialException as e:
        print(f"Serial Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_level_generation()