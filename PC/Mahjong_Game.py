import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import struct

# --- CONFIGURATION ---
CMD_START   = 0x01
CMD_RESET   = 0x02
CMD_SHUFFLE = 0x03
CMD_SELECT  = 0x04
CMD_MATCH   = 0x05

PACKET_SIZE = 52

# TILE CONFIGURATION
TILE_W = 50
TILE_H = 65
SHADOW_OFFSET = 4

# Color Palette
TILE_GROUPS = {
    0: ("Bamboo",  "#66BB6A"),
    1: ("Chars",   "#EF5350"),
    2: ("Circles", "#42A5F5"),
    3: ("Winds",   "#BDBDBD"),
    4: ("Dragons", "#FFEE58"),
    5: ("Flowers", "#AB47BC"),
    6: ("Seasons", "#FFA726")
}

# --- UART HANDLER (Keep exactly as you have it) ---
class UARTHandler:
    def __init__(self, port="COM3", baudrate=115200, root=None):
        self.port_name = port
        self.baudrate = baudrate
        self.ser = None
        self.root = root
        self.is_open = False

    def open_port(self):
        try:
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=2)
            self.is_open = True
            return True
        except serial.SerialException as e:
            self._show_error(f"Failed to open {self.port_name}:\n{e}")
            self.is_open = False
            return False

    def close_port(self):
        if self.ser and self.ser.is_open:
            try: self.ser.close()
            except: pass
        self.is_open = False

    def send_packet(self, cmd, data):
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
        try: return self.ser.read(count)
        except serial.SerialException:
            self._handle_disconnect(); return b""

    def reset_buffer(self):
        if self.ser and self.ser.is_open: self.ser.reset_input_buffer()

    def dtr_reset(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.dtr = False; time.sleep(0.1); self.ser.dtr = True; time.sleep(0.5)
            except: pass

    def _handle_disconnect(self):
        self.close_port()
        self._show_error("STM32 Disconnected!")

    def _show_error(self, msg):
        if self.root: self.root.after(0, lambda: messagebox.showerror("Connection Error", msg))


# --- MAIN GUI CLIENT (UPDATED) ---
class MahjongClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong Pyramid Visualizer")
        self.geometry("900x750")
        
        self.uart = UARTHandler(root=self)
        
        # --- NEW STATE VARIABLES ---
        self.current_board_data = None  # To store the 50 bytes locally
        self.hitboxes = []              # List of tuples: (x1, y1, x2, y2, index)
        self.selected_index = None      # Currently selected tile index (or None)
        
        self._init_ui()
        
        # Bind Mouse Click
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def _init_ui(self):
        # Toolbar
        frame_top = tk.Frame(self, bg="#f0f0f0", pady=10)
        frame_top.pack(fill=tk.X)
        
        tk.Label(frame_top, text="Port:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(frame_top, textvariable=self.port_var, width=10)
        self.combo_ports.pack(side=tk.LEFT, padx=5)
        self.refresh_ports()
        
        self.btn_connect = tk.Button(frame_top, text="Connect", command=self.toggle_connection, bg="#e0e0e0")
        self.btn_connect.pack(side=tk.LEFT, padx=5)
        
        self.btn_generate = tk.Button(frame_top, text="🎲 New Game", 
                                      command=self.send_start_command, 
                                      state=tk.DISABLED, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_generate.pack(side=tk.LEFT, padx=20)
        
        self.btn_shuffle = tk.Button(frame_top, text="🔀 Shuffle", 
                              command=self.send_shuffle_command, 
                              state=tk.DISABLED, bg="#2196F3", fg="white")
        self.btn_shuffle.pack(side=tk.LEFT, padx=5)

        # Canvas
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
            self.uart.close_port()
            self.btn_connect.config(text="Connect", bg="#e0e0e0")
            self.btn_generate.config(state=tk.DISABLED)
            self.btn_shuffle.config(state=tk.DISABLED)
        else:
            port = self.port_var.get()
            self.uart.port_name = port
            if self.uart.open_port():
                self.uart.dtr_reset()
                self.btn_connect.config(text="Disconnect", bg="#ffcccc")
                self.btn_generate.config(state=tk.NORMAL)
                self.btn_shuffle.config(state=tk.NORMAL)

    # --- CLICK HANDLER ---
    def on_canvas_click(self, event):
        """Handle mouse clicks to Select or Match tiles"""
        if not self.current_board_data: return

        # Iterate REVERSE to check Top-Most tiles first
        clicked_idx = -1
        for hb in reversed(self.hitboxes):
            x1, y1, x2, y2, idx = hb
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                clicked_idx = idx
                break
        
        if clicked_idx == -1: return # Clicked empty space

        # Logic State Machine
        if self.selected_index is None:
            # Nothing selected -> Send SELECT
            self.send_select_command(clicked_idx)
        else:
            if clicked_idx == self.selected_index:
                # Clicked same tile -> Deselect (locally)
                self.selected_index = None
                self.draw_pyramid(self.current_board_data)
            else:
                # Clicked different tile -> Send MATCH
                self.send_match_command(clicked_idx)

    # --- COMMANDS ---

    def send_start_command(self):
        if not self.uart.is_open: return
        self.uart.reset_buffer()
        self.uart.send_packet(CMD_START, 0x00)
        
        response = self.uart.read_bytes(PACKET_SIZE)
        if len(response) == PACKET_SIZE:
            self.selected_index = None # Reset selection
            self.draw_pyramid(response[1:51])
    
    def send_shuffle_command(self):
        if not self.uart.is_open: return
        self.uart.reset_buffer()
        self.uart.send_packet(CMD_SHUFFLE, 0x00)
        
        # Shuffle can return 3 bytes (Error) or 52 bytes (New Layout)
        # We read 3 first to check CMD
        header = self.uart.read_bytes(3)
        if len(header) < 3: return
        
        if header[1] == 0xFF:
            messagebox.showwarning("Shuffle", "Max shuffle limit reached!")
        else:
            # It's a full packet, read the rest (49 bytes)
            rest = self.uart.read_bytes(49)
            full_data = header + rest
            self.selected_index = None
            self.draw_pyramid(full_data[1:51])

    def send_select_command(self, index):
        """Sends CMD_SELECT (0x04)"""
        if not self.uart.is_open: return
        self.uart.reset_buffer()
        self.uart.send_packet(CMD_SELECT, index)
        
        # Expect 3 bytes response: [0x04, STATUS, CRC]
        resp = self.uart.read_bytes(3)
        if len(resp) == 3 and resp[1] == 0x00: # 0x00 is Success
            self.selected_index = index
            self.draw_pyramid(self.current_board_data) # Redraw to show highlight
        else:
            print("Selection Failed (STM32 rejected)")

    def send_match_command(self, index):
        """Sends CMD_MATCH (0x05)"""
        if not self.uart.is_open: return
        self.uart.reset_buffer()
        self.uart.send_packet(CMD_MATCH, index)
        
        # Expect 3 bytes response: [0x05, RESULT, CRC]
        resp = self.uart.read_bytes(3)
        if len(resp) == 3:
            result = resp[1]
            if result == 0x01: # Match Success!
                print("Match Success!")
                # Update Local Data: Remove both tiles
                board_arr = bytearray(self.current_board_data)
                board_arr[self.selected_index] = 0x00
                board_arr[index] = 0x00
                self.current_board_data = bytes(board_arr)
                
                self.selected_index = None
                self.draw_pyramid(self.current_board_data)
            else:
                print("Match Failed.")
                self.selected_index = None
                self.draw_pyramid(self.current_board_data) # Remove highlight

    # --- DRAWING ---

    def draw_pyramid(self, data):
        self.canvas.delete("all")
        self.hitboxes = []            # Clear hitboxes
        self.current_board_data = data # Sync data
        
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        start_x = cx - (2.5 * TILE_W)
        start_y = cy - (2.5 * TILE_H)

        def draw_tile(index, grid_x, grid_y, layer_z, offset_x_tiles, offset_y_tiles):
            byte = data[index]
            if byte == 0x00: return # Skip empty tiles

            group_id = (byte >> 5) & 0x07
            value = byte & 0x1F
            grp_name, color = TILE_GROUPS.get(group_id, ("???", "white"))

            x = start_x + (grid_x * TILE_W) + (offset_x_tiles * TILE_W)
            y = start_y + (grid_y * TILE_H) + (offset_y_tiles * TILE_H)
            
            z_shift = layer_z * SHADOW_OFFSET 
            x -= z_shift
            y -= z_shift

            # --- SAVE HITBOX ---
            # Save coordinates and index for click detection
            self.hitboxes.append((x, y, x+TILE_W, y+TILE_H, index))

            # --- SELECTION HIGHLIGHT ---
            border_color = "black"
            border_width = 1
            if index == self.selected_index:
                border_color = "#FF0000" # Red Highlight
                border_width = 3

            # Shadow
            self.canvas.create_rectangle(
                x + SHADOW_OFFSET, y + SHADOW_OFFSET, 
                x + TILE_W + SHADOW_OFFSET, y + TILE_H + SHADOW_OFFSET, 
                fill="#1a1a1a", outline=""
            )

            # Face
            self.canvas.create_rectangle(x, y, x+TILE_W, y+TILE_H, 
                                         fill="#f0f0f0", outline=border_color, width=border_width) 
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