import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time

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

class MahjongClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong Pyramid Visualizer")
        self.geometry("800x700")
        self.serial_port = None
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
        # Scrollbars for the canvas if the window is small
        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#333333") # Dark background for contrast
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_ports['values'] = ports
        if ports: self.combo_ports.current(0)

    def toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.btn_connect.config(text="Connect", bg="#e0e0e0")
            self.btn_generate.config(state=tk.DISABLED)
        else:
            try:
                port = self.port_var.get()
                self.serial_port = serial.Serial(port, 115200, timeout=2)
                # DTR Toggle to reset STM32
                self.serial_port.dtr = False
                time.sleep(0.1)
                self.serial_port.dtr = True
                
                self.btn_connect.config(text="Disconnect", bg="#ffcccc")
                self.btn_generate.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def send_start_command(self):
        if not self.serial_port: return
        try:
            self.serial_port.reset_input_buffer()
            # Send CMD: 0x01 0x00 0x01
            self.serial_port.write(bytes([CMD_START, 0x00, 0x01]))
            
            response = self.serial_port.read(PACKET_SIZE)
            if len(response) != PACKET_SIZE:
                messagebox.showwarning("Error", f"Expected {PACKET_SIZE} bytes, got {len(response)}")
                return
                
            self.draw_pyramid(response[1:51])
            
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))

    def draw_pyramid(self, data):
        self.canvas.delete("all")
        
        # Calculate center of canvas
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        
        # Base offset to center the 5x5 grid (approx width 250, height 325)
        start_x = cx - (2.5 * TILE_W)
        start_y = cy - (2.5 * TILE_H)

        # --- Helper to draw a single tile ---
        def draw_tile(index, grid_x, grid_y, layer_z, offset_x_tiles, offset_y_tiles):
            # 1. Decode Data
            byte = data[index]
            group_id = (byte >> 5) & 0x07
            value = byte & 0x1F
            grp_name, color = TILE_GROUPS.get(group_id, ("???", "white"))

            # 2. Calculate Screen Position
            # logic: Base + (GridPos * Size) + (LayerOffset * Size)
            x = start_x + (grid_x * TILE_W) + (offset_x_tiles * TILE_W)
            y = start_y + (grid_y * TILE_H) + (offset_y_tiles * TILE_H)
            
            # Shift up/left slightly for "Z-height" effect
            z_shift = layer_z * SHADOW_OFFSET 
            x -= z_shift
            y -= z_shift

            # 3. Draw Shadow (The "Side" of the tile)
            self.canvas.create_rectangle(
                x + SHADOW_OFFSET, y + SHADOW_OFFSET, 
                x + TILE_W + SHADOW_OFFSET, y + TILE_H + SHADOW_OFFSET, 
                fill="#1a1a1a", outline=""
            )

            # 4. Draw Tile Face
            tag = f"tile_{layer_z}_{grid_y}_{grid_x}"
            self.canvas.create_rectangle(x, y, x+TILE_W, y+TILE_H, fill="#f0f0f0", outline="black") # Face background
            self.canvas.create_rectangle(x+2, y+2, x+TILE_W-2, y+TILE_H-2, fill=color, outline="") # Inner Color

            # 5. Text
            self.canvas.create_text(x + TILE_W/2, y + TILE_H/2, text=str(value), 
                                    font=("Arial", 16, "bold"), fill="black")
            self.canvas.create_text(x + TILE_W/2, y + TILE_H - 10, text=grp_name[:3], 
                                    font=("Arial", 7), fill="black")

        # --- DRAW ORDER: Bottom to Top ---
        
        # Layer 1: 5x5 (Offset 0.0)
        idx = 0
        for r in range(5):
            for c in range(5):
                draw_tile(idx, c, r, 0, 0.0, 0.0)
                idx += 1
        
        # Layer 2: 4x4 (Offset 0.5)
        # Note: idx continues from 25
        for r in range(4):
            for c in range(4):
                draw_tile(idx, c, r, 1, 0.5, 0.5)
                idx += 1

        # Layer 3: 3x3 (Offset 1.0)
        # Note: idx continues from 41
        for r in range(3):
            for c in range(3):
                draw_tile(idx, c, r, 2, 1.0, 1.0)
                idx += 1

if __name__ == "__main__":
    app = MahjongClient()
    app.mainloop()