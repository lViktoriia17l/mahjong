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
            # Таймаут 1.5с дозволяє STM32 встигнути відповісти на складні команди
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=1.5)
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
        """Спроба відновити зв'язок з тим самим портом."""
        self.close_port()
        return self.open_port()

    def _calculate_crc(self, data: bytes):
        """Контрольна сума XOR (як вимагає протокол)."""
        crc = 0
        for byte in data:
            crc ^= byte
        return crc

    def send_packet(self, cmd, data_byte):
        """Відправляє [CMD, DATA, CRC]. Повертає True якщо успішно."""
        if not self.is_connected():
            return False
        try:
            payload = struct.pack("BB", cmd, data_byte)
            crc = self._calculate_crc(payload)
            self.ser.write(payload + struct.pack("B", crc))
            self.ser.flush()
            return True
        except (serial.SerialException, AttributeError):
            self.is_open = False
            return False

    def read_packet_strictly(self, count):
        """Читає 'count' байтів, перевіряє CRC. Повертає Payload або None."""
        if not self.is_connected():
            return None
        try:
            data = self.ser.read(count)
            if len(data) == count:
                if self._calculate_crc(data[:-1]) == data[-1]:
                    return data[:-1]
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