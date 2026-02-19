import tkinter as tk
from tkinter import ttk, messagebox
import time
from UART_handler import UARTHandler

# --- CONFIGURATION ---
CMD_START   = 0x01
CMD_RESET   = 0x02
CMD_SHUFFLE = 0x03
CMD_SELECT  = 0x04
CMD_MATCH   = 0x05

PACKET_SIZE = 52
TILE_W = 50
TILE_H = 65
SHADOW_OFFSET = 4

TILE_GROUPS = {
    0: ("Bamboo",  "#66BB6A"),
    1: ("Chars",   "#EF5350"),
    2: ("Circles", "#42A5F5"),
    3: ("Winds",   "#BDBDBD"),
    4: ("Dragons", "#FFEE58"),
    5: ("Flowers", "#AB47BC"),
    6: ("Seasons", "#FFA726")
}

# --- SCREEN 1: MAIN MENU ---
class MainMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        
        tk.Label(self, text="STM32 Mahjong Console", font=("Arial", 28, "bold"), bg="#f0f0f0", fg="#333").pack(pady=(100, 10))
        tk.Label(self, text="Select your device port to begin", font=("Arial", 12), bg="#f0f0f0", fg="#666").pack(pady=(0, 30))

        self.lbl_status = tk.Label(self, text="Ready", font=("Arial", 10, "italic"), bg="#f0f0f0", fg="black")
        self.lbl_status.pack(pady=(0, 20))

        frame_controls = tk.Frame(self, bg="#f0f0f0")
        frame_controls.pack()

        tk.Label(frame_controls, text="COM Port:", font=("Arial", 12), bg="#f0f0f0").grid(row=0, column=0, padx=10)
        
        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(frame_controls, textvariable=self.port_var, width=15, state="readonly", font=("Arial", 11))
        self.combo_ports.grid(row=0, column=1, padx=10)
        
        btn_refresh = tk.Button(frame_controls, text="↻", command=self.refresh_ports, font=("Arial", 12, "bold"), width=3)
        btn_refresh.grid(row=0, column=2, padx=5)

        self.btn_connect = tk.Button(self, text="CONNECT & PLAY", command=self.connect, 
                                     bg="#4CAF50", fg="white", font=("Arial", 14, "bold"), 
                                     width=20, pady=10, relief="flat")
        self.btn_connect.pack(pady=40)

    def refresh_ports(self):
        ports = UARTHandler.list_available_ports()
        self.combo_ports['values'] = ports
        if ports: 
            if not self.port_var.get() in ports:
                self.combo_ports.current(0)
        else: 
            self.port_var.set("No Ports Found")

    def connect(self):
        port = self.port_var.get()
        if not port or port == "No Ports Found":
            messagebox.showwarning("Error", "Please select a valid COM port.")
            return

        self.controller.cancel_auto_reconnect()
        self.lbl_status.config(text="Connecting...", fg="black")

        self.controller.uart.port_name = port
        if self.controller.uart.open_port():
            self.controller.uart.dtr_reset()
            self.lbl_status.config(text="Ready", fg="black")
            self.controller.show_game()
        else:
            messagebox.showerror("Error", f"Could not connect to {port}")
            self.lbl_status.config(text="Connection Failed", fg="red")


# --- SCREEN 2: GAME INTERFACE ---
class GameInterface(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.current_board_data = None
        self.hitboxes = []
        self.selected_index = None
        self.error_tiles = [] # Tracks tiles that should blink red

        toolbar = tk.Frame(self, bg="#ddd", pady=10)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="← Disconnect", command=self.disconnect, bg="#ffcccc").pack(side=tk.LEFT, padx=10)
        tk.Button(toolbar, text="🎲 New Game", command=self.send_start_command, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        tk.Button(toolbar, text="🔀 Shuffle", command=self.send_shuffle_command, bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=5)

        self.canvas = tk.Canvas(self, bg="#333333")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    # --- CONSOLE LOGGER ---
    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[Game] {timestamp} - {msg}")

    # --- BLINK LOGIC ---
    def show_error_blink(self, indices):
        """Makes specific tiles blink red briefly."""
        self.error_tiles = indices
        self.draw_pyramid(self.current_board_data)
        self.after(400, self.clear_error_blink) # Clear after 400ms

    def clear_error_blink(self):
        """Removes the red error highlight."""
        self.error_tiles = []
        if self.current_board_data:
            self.draw_pyramid(self.current_board_data)

    def disconnect(self):
        self.log("Disconnected from STM32.")
        self.controller.uart.close_port()
        self.controller.show_menu()
        self.canvas.delete("all")
        self.current_board_data = None

    # --- GAME LOGIC ---
    def send_start_command(self):
        if not self.controller.uart.is_open: return
        self.log("Requesting New Game Layout...")
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_START, 0x00):
            self.controller.trigger_auto_reconnect(); return
            
        response = self.controller.uart.read_bytes(PACKET_SIZE)
        if response is None: 
            self.controller.trigger_auto_reconnect(); return
            
        if len(response) == PACKET_SIZE:
            self.log("New Game Generated Successfully!")
            self.selected_index = None
            self.draw_pyramid(response[1:51])
    
    def send_shuffle_command(self):
        if not self.controller.uart.is_open: return
        self.log("Requesting Board Shuffle...")
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_SHUFFLE, 0x00):
            self.controller.trigger_auto_reconnect(); return
        
        header = self.controller.uart.read_bytes(3)
        if header is None:
            self.controller.trigger_auto_reconnect(); return
            
        if len(header) < 3: return
        
        if header[1] == 0xFF:
            self.log("SHUFFLE REJECTED: Max limit reached.")
            messagebox.showwarning("Shuffle", "Max shuffle limit reached!")
        else:
            self.log("SHUFFLE APPROVED! Processing new layout.")
            rest = self.controller.uart.read_bytes(49)
            if rest is None:
                self.controller.trigger_auto_reconnect(); return
            full_data = header + rest
            self.selected_index = None
            self.draw_pyramid(full_data[1:51])

    def on_canvas_click(self, event):
        if not self.current_board_data: return

        clicked_idx = -1
        for hb in reversed(self.hitboxes):
            x1, y1, x2, y2, idx = hb
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                clicked_idx = idx
                break
        
        if clicked_idx == -1: return

        if self.selected_index is None:
            self.send_select_command(clicked_idx)
        else:
            if clicked_idx == self.selected_index:
                self.log(f"Deselected Tile {self.selected_index}.")
                self.selected_index = None
                self.draw_pyramid(self.current_board_data)
            else:
                self.send_match_command(clicked_idx)

    def send_select_command(self, index):
        self.log(f"Attempting to select Tile {index}...")
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_SELECT, index):
            self.controller.trigger_auto_reconnect(); return
            
        resp = self.controller.uart.read_bytes(3)
        if resp is None:
            self.controller.trigger_auto_reconnect(); return
            
        if len(resp) == 3 and resp[1] == 0x00:
            self.log(f"SUCCESS: Tile {index} is exposed and selected.")
            self.selected_index = index
            self.draw_pyramid(self.current_board_data)
        else:
            self.log(f"REJECTED: Tile {index} is blocked.")
            self.show_error_blink([index])

    def send_match_command(self, index):
        self.log(f"Attempting to match Tile {self.selected_index} with Tile {index}...")
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_MATCH, index):
            self.controller.trigger_auto_reconnect(); return
            
        resp = self.controller.uart.read_bytes(3)
        if resp is None:
            self.controller.trigger_auto_reconnect(); return
            
        if len(resp) == 3 and resp[1] == 0x01:
            self.log(f"MATCH SUCCESS! Tiles {self.selected_index} and {index} removed.")
            board_arr = bytearray(self.current_board_data)
            board_arr[self.selected_index] = 0x00
            board_arr[index] = 0x00
            self.current_board_data = bytes(board_arr)
            
            self.selected_index = None
            self.draw_pyramid(self.current_board_data)
        else:
            self.log("MATCH FAILED: Tiles do not match or target is blocked.")
            
            # 1. Save the first tile's index
            old_selection = self.selected_index
            
            # 2. CLEAR the active selection so the Cyan color goes away
            self.selected_index = None
            
            # 3. Trigger the Red Blink on BOTH the old tile and the new clicked tile
            self.show_error_blink([old_selection, index])

    def draw_pyramid(self, data):
        self.canvas.delete("all")
        self.hitboxes = []
        self.current_board_data = data
        
        self.update_idletasks()
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        start_x = cx - (2.5 * TILE_W)
        start_y = cy - (2.5 * TILE_H)

        def draw_tile(index, grid_x, grid_y, layer_z, offset_x_tiles, offset_y_tiles):
            byte = data[index]
            if byte == 0x00: return

            group_id = (byte >> 5) & 0x07
            value = byte & 0x1F
            grp_name, color = TILE_GROUPS.get(group_id, ("???", "white"))

            x = start_x + (grid_x * TILE_W) + (offset_x_tiles * TILE_W)
            y = start_y + (grid_y * TILE_H) + (offset_y_tiles * TILE_H)
            
            z_shift = layer_z * SHADOW_OFFSET 
            x -= z_shift
            y -= z_shift

            self.hitboxes.append((x, y, x+TILE_W, y+TILE_H, index))

            # --- DYNAMIC HIGHLIGHT COLORS (UPDATED) ---
            border_color = "black"
            border_width = 1
            
            # Rule 1: Priority goes to Errors (Red)
            if index in self.error_tiles:
                border_color = "#FF0000" # Red
                border_width = 3
            # Rule 2: Then check for Valid Selections (Cyan)
            elif index == self.selected_index:
                border_color = "#00FFFF" # Cyan
                border_width = 3

            self.canvas.create_rectangle(x + SHADOW_OFFSET, y + SHADOW_OFFSET, x + TILE_W + SHADOW_OFFSET, y + TILE_H + SHADOW_OFFSET, fill="#1a1a1a", outline="")
            self.canvas.create_rectangle(x, y, x+TILE_W, y+TILE_H, fill="#f0f0f0", outline=border_color, width=border_width) 
            self.canvas.create_rectangle(x+2, y+2, x+TILE_W-2, y+TILE_H-2, fill=color, outline="") 
            self.canvas.create_text(x + TILE_W/2, y + TILE_H/2, text=str(value), font=("Arial", 16, "bold"), fill="black")
            self.canvas.create_text(x + TILE_W/2, y + TILE_H - 10, text=grp_name[:3], font=("Arial", 7), fill="black")

        idx = 0
        for r in range(5):
            for c in range(5): draw_tile(idx, c, r, 0, 0.0, 0.0); idx += 1
        for r in range(4):
            for c in range(4): draw_tile(idx, c, r, 1, 0.5, 0.5); idx += 1
        for r in range(3):
            for c in range(3): draw_tile(idx, c, r, 2, 1.0, 1.0); idx += 1


# --- MAIN APP CONTROLLER ---
class MahjongApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong Visualizer")
        self.geometry("900x750")
        
        self.uart = UARTHandler()
        self.is_reconnecting = False
        self.reconnect_port = ""
        
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.menu_view = MainMenu(self.container, self)
        self.game_view = GameInterface(self.container, self)

        self.show_menu()

    def show_menu(self):
        self.game_view.pack_forget()
        self.menu_view.pack(fill="both", expand=True)
        self.menu_view.refresh_ports()

    def show_game(self):
        self.menu_view.pack_forget()
        self.game_view.pack(fill="both", expand=True)
        self.after(200, self.game_view.send_start_command)

    def trigger_auto_reconnect(self):
        if self.is_reconnecting: return
        self.is_reconnecting = True
        self.reconnect_port = self.uart.port_name
        self.uart.close_port()
        
        self.show_menu()
        self.menu_view.lbl_status.config(text=f"Connection lost! Auto-reconnecting to {self.reconnect_port}...", fg="red")
        messagebox.showwarning("Connection Lost", f"No response from STM32 on {self.reconnect_port}.\n\nPlease ensure it is plugged in.\nThe app will attempt to automatically reconnect.")
        self.attempt_reconnect()

    def attempt_reconnect(self):
        if not self.is_reconnecting: return
        
        self.menu_view.refresh_ports()
        ports = self.menu_view.combo_ports['values']
        
        if self.reconnect_port in ports:
            self.uart.port_name = self.reconnect_port
            if self.uart.open_port():
                self.uart.dtr_reset()
                self.is_reconnecting = False
                self.menu_view.lbl_status.config(text="Ready", fg="black")
                messagebox.showinfo("Reconnected", "Successfully reconnected to STM32!")
                self.show_game()
                return
        
        current_text = self.menu_view.lbl_status.cget("text")
        new_text = current_text + "." if len(current_text) < 65 else f"Auto-reconnecting to {self.reconnect_port}."
        self.menu_view.lbl_status.config(text=new_text)
        
        self.after(2000, self.attempt_reconnect)

    def cancel_auto_reconnect(self):
        self.is_reconnecting = False


if __name__ == "__main__":
    app = MahjongApp()
    app.mainloop()