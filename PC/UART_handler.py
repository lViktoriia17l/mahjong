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
            # Базовий таймаут низького рівня ставимо невеликим (0.1с)
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=0.1)
            self.is_open = True
            return True
        except Exception:
            self.is_open = False
            return False

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
            # FIX: Send ONLY a 3-byte packet to prevent STM32 buffer desynchronization.
            # Since STM32 is strictly expecting 3 bytes, we drop the string payload 
            # and just send a dummy data byte (0x00).
            
            # Stage 1: Send Header [CMD] [0x00]
            header = struct.pack("BB", cmd, 0x00)
            header_crc = self._calculate_crc(header)
            
            # Send exactly 3 bytes: [CMD] [0x00] [CRC]
            self.ser.write(header + struct.pack("B", header_crc))
            self.ser.flush()

            # Note: We removed Stage 2 (the name bytes) because the STM32 
            # does not currently have a buffer to absorb them.
            
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
                # Перевіряємо, чи не вийшов загальний час очікування
                if (time.time() - start_time) > timeout_sec:
                    return None 
                
                # Читаємо те, що вже є в буфері (або чекаємо 0.1с згідно timeout в open_port)
                remaining = count - len(buffer)
                chunk = self.ser.read(remaining)
                if chunk:
                    buffer += chunk
            
            # Перевірка CRC
            if len(buffer) == count:
                if self._calculate_crc(buffer[:-1]) == buffer[-1]:
                    return buffer[:-1] # Повертаємо дані без байта CRC
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