import serial
import struct
from tkinter import messagebox
import time

class UARTHandler:
    """
    Обробка COM-порту для STM32 з pop-up при від'єднанні.
    """

    def __init__(self, port="COM3", baudrate=115200, root=None):
        self.port_name = port
        self.baudrate = baudrate
        self.ser = None
        self.root = root
        self.is_open = False

    def open_port(self):
        try:
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=0.1)
            self.is_open = True
        except serial.SerialException as e:
            self._show_error(f"Не вдалося відкрити порт {self.port_name}:\n{e}")
            self.is_open = False

    def close_port(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        self.is_open = False

    def send_packet(self, cmd, data):
        """Відправляє пакет і ловить від’єднання"""
        if not self.ser or not self.ser.is_open:
            self._handle_disconnect()
            return
        try:
            crc = cmd ^ data
            packet = struct.pack("BBB", cmd, data, crc)
            self.ser.write(packet)
        except serial.SerialException:
            self._handle_disconnect()

    def read_bytes(self, count):
        if not self.ser or not self.ser.is_open:
            self._handle_disconnect()
            return b""
        try:
            return self.ser.read(count)
        except serial.SerialException:
            self._handle_disconnect()
            return b""

    def _handle_disconnect(self):
        self.close_port()
        self._show_error("STM32 від'єднано")

    def _show_error(self, msg):
        if self.root:
            self.root.after(0, lambda: messagebox.showerror("Connection Lost", msg))
