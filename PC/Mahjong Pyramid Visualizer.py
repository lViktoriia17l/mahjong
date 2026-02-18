import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import struct

# --- CONFIGURATION ---
CMD_START = 0x01
PACKET_SIZE = 52

# TILE CONFIGURATION
TILE_W = 50
TILE_H = 65
SHADOW_OFFSET = 4  # Depth effect in pixels

# Color Palette (Group ID -> (Name, Color))
TILE_GROUPS = {
    0: ("Bamboo",  "#66BB6A"), # Green
    1: ("Chars",   "#EF5350"), # Red
    2: ("Circles", "#42A5F5"), # Blue
    3: ("Winds",   "#BDBDBD"), # Gray
    4: ("Dragons", "#FFEE58"), # Yellow
    5: ("Flowers", "#AB47BC"), # Purple
    6: ("Seasons", "#FFA726")  # Orange
}

# --- UART HANDLER CLASS (Integrated) ---
class UARTHandler:
    """
    Handles COM port operations with error handling and pop-ups.
    """
    def __init__(self, port="COM3", baudrate=115200, root=None):
        self.port_name = port
        self.baudrate = baudrate
        self.ser = None
        self.root = root
        self.is_open = False

    def open_port(self):
        try:
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=2) # Timeout 2s for game logic
            self.is_open = True
            return True
        except serial.SerialException as e:
            self._show_error(f"Failed to open {self.port_name}:\n{e}")
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
        """Sends [CMD, DATA, CRC]"""
        if not self.ser or not self.ser.is_open:
            self._handle_disconnect()
            return
        try:
            # CRC Calculation: XOR
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

    def reset_buffer(self):
        if self.ser and self.ser.is_open:
            self.ser.reset_input_buffer()

    def dtr_reset(self):
        """Toggles DTR to reset connected STM32/Arduino boards"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.dtr = False
                time.sleep(0.1)
                self.ser.dtr = True
                time.sleep(0.5) # Wait for boot
            except:
                pass

    def _handle_disconnect(self):
        self.close_port()
        self._show_error("STM32 Disconnected!")

    def _show_error(self, msg):
        if self.root:
            # Schedule the messagebox on the main UI thread
            self.root.after(0, lambda: messagebox.showerror("Connection Error", msg))

# --- MAIN GUI CLIENT ---
class MahjongClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong Pyramid Visualizer")
        self.geometry("800x700")
        
        # Initialize UART Handler with reference to self (for popups)
        self.uart = UARTHandler(root=self)
        
        self._init_ui()

    def _init_ui(self):
        # --- Toolbar ---
        frame_top = tk.Frame(self, bg="#f0f0f0", pady=10)
        frame_top.pack(fill=tk.X)
        
        tk.Label(frame_top, text="Port:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(frame_top, textvariable=self.port_var, width=10)
        self.combo_ports.pack(side=tk.LEFT, padx=5)
        self.refresh_ports()
        
        self.btn_connect = tk.Button(frame_top, text="Connect", command=self.toggle_connection, bg="#e0e0e0")
        self.btn_connect.pack(side=tk.LEFT, padx=5)
        
        self.btn_generate = tk.Button(frame_top, text="🎲 Generate Pyramid", 
                                      command=self.send_start_command, 
                                      state=tk.DISABLED, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_generate.pack(side=tk.LEFT, padx=20)

        # --- Main Canvas ---
        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#333333") 
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_ports['values'] = ports
        if ports: self.combo_ports.current(0)

    def toggle_connection(self):
        if self.uart.is_open:
            # Disconnect
            self.uart.close_port()
            self.btn_connect.config(text="Connect", bg="#e0e0e0")
            self.btn_generate.config(state=tk.DISABLED)
        else:
            # Connect
            port = self.port_var.get()
            self.uart.port_name = port
            
            if self.uart.open_port():
                # Perform DTR Reset to ensure clean start
                self.uart.dtr_reset()
                
                self.btn_connect.config(text="Disconnect", bg="#ffcccc")
                self.btn_generate.config(state=tk.NORMAL)

    def send_start_command(self):
        if not self.uart.is_open: return
        
        # 1. Clear Buffer
        self.uart.reset_buffer()
        
        # 2. Send Packet using UARTHandler
        # We send CMD_START (0x01) and Dummy Data (0x00)
        # The handler automatically calculates CRC: 0x01 ^ 0x00 = 0x01
        self.uart.send_packet(CMD_START, 0x00)
        
        # 3. Read Response
        response = self.uart.read_bytes(PACKET_SIZE)
        
        if len(response) != PACKET_SIZE:
            print("Protocol Error", f"Expected {PACKET_SIZE} bytes, got {len(response)}")
            return
            
        # 4. Draw (Slice out the 50 data bytes: index 1 to 51)
        self.draw_pyramid(response[1:51])

    def draw_pyramid(self, data):
        self.canvas.delete("all")
        
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        
        start_x = cx - (2.5 * TILE_W)
        start_y = cy - (2.5 * TILE_H)

        def draw_tile(index, grid_x, grid_y, layer_z, offset_x_tiles, offset_y_tiles):
            byte = data[index]
            group_id = (byte >> 5) & 0x07
            value = byte & 0x1F
            grp_name, color = TILE_GROUPS.get(group_id, ("???", "white"))

            x = start_x + (grid_x * TILE_W) + (offset_x_tiles * TILE_W)
            y = start_y + (grid_y * TILE_H) + (offset_y_tiles * TILE_H)
            
            z_shift = layer_z * SHADOW_OFFSET 
            x -= z_shift
            y -= z_shift

            # Shadow
            self.canvas.create_rectangle(
                x + SHADOW_OFFSET, y + SHADOW_OFFSET, 
                x + TILE_W + SHADOW_OFFSET, y + TILE_H + SHADOW_OFFSET, 
                fill="#1a1a1a", outline=""
            )

            # Face
            self.canvas.create_rectangle(x, y, x+TILE_W, y+TILE_H, fill="#f0f0f0", outline="black") 
            self.canvas.create_rectangle(x+2, y+2, x+TILE_W-2, y+TILE_H-2, fill=color, outline="") 

            # Text
            self.canvas.create_text(x + TILE_W/2, y + TILE_H/2, text=str(value), 
                                    font=("Arial", 16, "bold"), fill="black")
            self.canvas.create_text(x + TILE_W/2, y + TILE_H - 10, text=grp_name[:3], 
                                    font=("Arial", 7), fill="black")

        # Layer 1
        idx = 0
        for r in range(5):
            for c in range(5):
                draw_tile(idx, c, r, 0, 0.0, 0.0)
                idx += 1
        
        # Layer 2
        for r in range(4):
            for c in range(4):
                draw_tile(idx, c, r, 1, 0.5, 0.5)
                idx += 1

        # Layer 3
        for r in range(3):
            for c in range(3):
                draw_tile(idx, c, r, 2, 1.0, 1.0)
                idx += 1

if __name__ == "__main__":
    app = MahjongClient()
    app.mainloop()