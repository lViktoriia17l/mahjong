import serial
import serial.tools.list_ports
import struct
import time

class UARTHandler:
    def __init__(self, port="COM3", baudrate=115200):
        self.port_name = port
        self.baudrate = baudrate
        self.ser = None
        self.is_open = False

    @staticmethod
    def list_available_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def open_port(self):
        try:
            # Basic timeout of 0.1s for read operations, to prevent blocking indefinitely
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=0.1)
            self.is_open = True
            return True
        except Exception:
            self.is_open = False
            return False
        
    def check_connection(self):
        """Actively checks if the physical serial device is still present."""
        if not self.is_open or not self.ser:
            return False
        try:
            _ = self.ser.in_waiting
            return True
        except (serial.SerialException, OSError, AttributeError):
            self.is_open = False
            return False

    def check_for_starting_packet(self):
        """
        Reads the buffer after a reconnect. If there is data (a starting packet),
        or if the game clock reset, it means the STM32 lost power and rebooted.
        """
        if not self.is_connected(): return True 
        try:
            # 1. Listen for any spontaneous boot bytes (starting packet)
            time.sleep(0.5) 
            if self.ser.in_waiting > 0:
                _ = self.ser.read(self.ser.in_waiting)
                self.reset_buffer()
                return True 
                
            # 2. Fallback: actively verify if RAM was wiped by checking the clock
            self.reset_buffer()
            payload = struct.pack("BB", 0x0B, 0x00) # CMD_GET_TIME
            crc = self._calculate_crc(payload)
            self.ser.write(payload + struct.pack("B", crc))
            self.ser.flush()
            
            resp = self.read_packet_strictly(52, timeout_sec=1.0)
            
            # ---> THE FIX IS HERE <---
            if resp is None:
                # If the board doesn't answer the ping at all, its UART is dead. 
                # Return True to force the game to exit to the main menu!
                return True 
                
            if resp and resp[0] == 0x0B:
                elapsed = int.from_bytes(resp[1:5], "big")
                if elapsed < 2:  # Clock reset to 0 means power was lost!
                    return True
            return False
        except Exception:
            return True

    def close_port(self):
        if self.ser and self.ser.is_open:
            try: self.ser.close()
            except: pass
        self.is_open = False

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def reconnect(self):
        self.close_port()
        return self.open_port()

    def _calculate_crc(self, data: bytes):
        crc = 0
        for byte in data:
            crc ^= byte
        return crc

    def send_packet(self, cmd, data_byte):
        if not self.is_connected(): return False
        try:
            payload = struct.pack("BB", cmd, data_byte)
            crc = self._calculate_crc(payload)
            self.ser.write(payload + struct.pack("B", crc))
            self.ser.flush()
            return True
        except:
            self.is_open = False
            return False

    def send_name_packet(self, cmd, name_str):
        if not self.is_connected(): return False
        try:
            # Converting the name string to bytes, ensuring it's ASCII and max 10 bytes long
            name_bytes = name_str.encode('ascii', errors='ignore')[:10]
            name_len = len(name_bytes)

            # Sending the header (cmd + name length) with its own CRC
            header = struct.pack("BB", cmd, name_len)
            header_crc = self._calculate_crc(header)
            self.ser.write(header + struct.pack("B", header_crc))
            self.ser.flush()

            # Critical pause: Give STM32 50 ms, to prepare for string receive
            time.sleep(0.05) 

            # Sending the name bytes with its own CRC
            payload_crc = self._calculate_crc(name_bytes)
            self.ser.write(name_bytes + struct.pack("B", payload_crc))
            self.ser.flush()
            
            return True
        except:
            self.is_open = False
            return False

    def read_packet_strictly(self, count, timeout_sec=2.0):

        if not self.is_connected(): return None
        
        start_time = time.time()
        buffer = b""
        
        try:
            while len(buffer) < count:
                # Checking, if waiting time isn't over
                if (time.time() - start_time) > timeout_sec:
                    return None 
                
                # Reading the buffer (or wait 0.1s timeout in open_port)
                remaining = count - len(buffer)
                chunk = self.ser.read(remaining)
                if chunk:
                    buffer += chunk
            
            # Check CRC
            if len(buffer) == count:
                if self._calculate_crc(buffer[:-1]) == buffer[-1]:
                    return buffer[:-1] # Returning data without CRC byte
            return None
            
        except (serial.SerialException, AttributeError):
            self.is_open = False
            return None

    def reset_buffer(self): 
        if self.is_connected():
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except: pass

    def dtr_reset(self):
        if self.is_connected():
            try:
                self.ser.dtr = False
                time.sleep(0.1)
                self.ser.dtr = True
            except: pass