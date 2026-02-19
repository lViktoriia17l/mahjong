import serial
import serial.tools.list_ports
import struct
import time

class UARTHandler:
    """
    Handles COM port operations, packet construction (with CRC), 
    and disconnect detection.
    """
    def __init__(self, port="COM3", baudrate=115200):
        self.port_name = port
        self.baudrate = baudrate
        self.ser = None
        self.is_open = False

    @staticmethod
    def list_available_ports():
        """Returns a list of available COM ports string names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def open_port(self):
        try:
            # Timeout set to 2s. If no data arrives in 2s, it's considered disconnected.
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=2)
            self.is_open = True
            return True
        except serial.SerialException:
            self.is_open = False
            return False

    def close_port(self):
        if self.ser and self.ser.is_open:
            try: 
                self.ser.close()
            except: 
                pass
        self.is_open = False

    def send_packet(self, cmd, data):
        """Returns True if successful, False if disconnected."""
        if not self.ser or not self.ser.is_open: 
            return False
        try:
            crc = cmd ^ data
            packet = struct.pack("BBB", cmd, data, crc)
            self.ser.write(packet)
            return True
        except serial.SerialException:
            self.close_port()
            return False

    def read_bytes(self, count):
        """Returns bytes if successful, None if timeout or disconnected."""
        if not self.ser or not self.ser.is_open: 
            return None
        try:
            data = self.ser.read(count)
            # If we asked for bytes but got 0 after the 2-second timeout, the STM32 stopped responding.
            if len(data) == 0:
                return None 
            return data
        except serial.SerialException:
            self.close_port()
            return None

    def reset_buffer(self):
        if self.ser and self.ser.is_open:
            try: 
                self.ser.reset_input_buffer()
            except: 
                pass

    def dtr_reset(self):
        """Toggles DTR to physically reset connected STM32/Arduino boards."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.dtr = False
                time.sleep(0.1)
                self.ser.dtr = True
                time.sleep(0.5) 
            except: 
                pass