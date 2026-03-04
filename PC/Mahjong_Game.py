import tkinter as tk
from tkinter import ttk, messagebox
import time
import struct
from UART_handler import UARTHandler

# --- CONFIGURATION ---
CMD_START = 0x01
CMD_RESET = 0x02
CMD_SHUFFLE = 0x03
CMD_SELECT = 0x04
CMD_MATCH = 0x05
CMD_GIVE_UP = 0x07
CMD_HINT = 0x08
CMD_SET_NAME = 0x09
CMD_GET_TIME = 0x0B
CMD_GET_LEADERS = 0x0C

PACKET_SIZE = 52  # 50 tiles + 1 byte CMD + 1 byte CRC
TILE_W, TILE_H, SHADOW_OFFSET = 50, 65, 4

TILE_GROUPS = {
    0: ("Bamboo", "#66BB6A"), 1: ("Chars", "#EF5350"), 2: ("Circles", "#42A5F5"),
    3: ("Winds", "#BDBDBD"), 4: ("Dragons", "#FFEE58"), 5: ("Flowers", "#AB47BC"), 6: ("Seasons", "#FFA726")
}

# --- MAIN MENU ---
class MainMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        
        tk.Label(self, text="STM32 Mahjong", font=("Arial", 28, "bold"), bg="#f0f0f0").pack(pady=(100, 10))
        self.lbl_status = tk.Label(self, text="Ready", font=("Arial", 10, "italic"), bg="#f0f0f0")
        self.lbl_status.pack(pady=(0, 20))

        frame_name = tk.Frame(self, bg="#f0f0f0")
        frame_name.pack(pady=(10, 20))
        tk.Label(frame_name, text="Player Name: (Up to 10 characters)", font=("Arial", 12), bg="#f0f0f0").grid(row=0, column=0, padx=5)
        self.player_name_var = tk.StringVar(value="Player1")
        self.entry_name = tk.Entry(frame_name, textvariable=self.player_name_var, font=("Arial", 12), width=15)
        self.entry_name.grid(row=0, column=1, padx=5)

        frame_layout = tk.Frame(self, bg="#f0f0f0")
        frame_layout.pack(pady=(5, 15))
        tk.Label(frame_layout, text="Layout:", font=("Arial", 12), bg="#f0f0f0").grid(row=0, column=0, padx=5)
        self.layout_var = tk.StringVar(value="Square Pyramid")
        self.combo_layout = ttk.Combobox(frame_layout, textvariable=self.layout_var, values=["Square Pyramid", "Triangle Pyramid"], state="readonly", width=19)
        self.combo_layout.grid(row=0, column=1)

        # Обмеження вводу до 10 символів
        self.entry_name.configure(
            validate="key",
            validatecommand=(self.register(self.limit_name), "%P")
        )

        frame_port = tk.Frame(self, bg="#f0f0f0")
        frame_port.pack()
        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(frame_port, textvariable=self.port_var, width=15, state="readonly")
        self.combo_ports.grid(row=0, column=0, padx=10)
        
        tk.Button(frame_port, text="↻", command=self.refresh_ports).grid(row=0, column=1)
        tk.Button(self, text="CONNECT & PLAY", command=self.connect, bg="#4CAF50", fg="white", font=("Arial", 14, "bold"), pady=10).pack(pady=40)

    def limit_name(self, new_value):
        return len(new_value) <= 10
    
    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def refresh_ports(self):
        ports = UARTHandler.list_available_ports()
        self.combo_ports['values'] = ports
        if ports: self.combo_ports.current(0)
        else: self.port_var.set("No Ports Found")

    def connect(self):
        self.log("Attempting to connect...")
        port = self.port_var.get()
        name = self.player_name_var.get().strip()

        if not name:
            messagebox.showwarning("Input Error", "Please enter a player name!")
            return

        if not port or port == "No Ports Found": 
            self.log("No port selected or available.")
            return
            
        self.controller.uart.port_name = port
        if self.controller.uart.open_port():
            self.log(f"Connected to {port}")
            self.controller.uart.dtr_reset()
            time.sleep(1.5)
            
            self.send_player_name(name)
            
            # Save Layout choice to the game view for later use
            self.controller.game_view.layout_id = 1 if self.layout_var.get() == "Symmetrical Pyramid" else 0
            
            self.controller.game_view.player_name = name 
            self.controller.show_game()

    def send_player_name(self, name):
        self.log(f"Registering player name: {name}")
        self.controller.uart.reset_buffer()
        
        if self.controller.uart.send_name_packet(CMD_SET_NAME, name):
            # Чекаємо 3-байтовий ACK від STM32
            resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
            if resp and resp[0] == CMD_SET_NAME and resp[1] == 0x00:
                self.log(f"Name '{name}' successfully saved to STM32 RAM.")
            else:
                self.log("Warning: STM32 did not acknowledge the name.")
        else:
            self.log("Failed to send name packet.")

# --- GAME INTERFACE ---
class GameInterface(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.timer_active = False
        self.current_board_data = None
        self.hitboxes = []
        self.selected_index = None
        self.error_tiles = []
        self.shuffles_left = 5
        self.hint_tiles = []
        
        self.info_frame = tk.Frame(self, bg="#f0f0f0")
        self.info_frame.pack(fill=tk.X)
        self.timer_label = tk.Label(self.info_frame, text="Time: 00:00", font=("Arial", 12, "bold"), bg="#f0f0f0")
        self.timer_label.pack(side="left", padx=20)

        toolbar = tk.Frame(self, bg="#ddd", pady=10)
        toolbar.pack(fill=tk.X)
        tk.Button(toolbar, text="← Exit", command=self.exit_to_menu).pack(side=tk.LEFT, padx=10)
        tk.Button(toolbar, text="🔄 Reset", command=self.send_reset_command, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=10)
        self.btn_shuffle = tk.Button(toolbar, text="🔀 Shuffle", command=self.send_shuffle_command, bg="#2196F3", fg="white")
        self.btn_shuffle.pack(side=tk.LEFT, padx=5)
        self.lbl_shuffles = tk.Label(toolbar, text=f"Attempts: {self.shuffles_left}", font=("Arial", 10, "bold"), bg="#ddd")
        self.lbl_shuffles.pack(side=tk.LEFT, padx=15)
        tk.Button(toolbar, text="🏳 Give Up", command=self.send_giveup_command, bg="#607D8B", fg="white").pack(side=tk.LEFT, padx=10)
        tk.Button(toolbar, text="💡 Hint", command=self.request_hint, bg="#FFEB3B", fg="black").pack(side=tk.LEFT, padx=10)

        self.canvas = tk.Canvas(self, bg="#333333")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
        
    def exit_to_menu(self):
        self.log("Exiting to menu...")
        self.timer_active = False 
        self.controller.uart.close_port()
        self.controller.show_menu()

    def handle_error(self, retry_func, *args):
        self.controller.uart_busy = False # Release lock on error
        self.log("Communication error! Opening dialog...")
        answer = messagebox.askretrycancel(
            "Connection Lost", 
            "STM32 is not responding. Check the cable and click 'Retry' to continue."
        )
        if answer:
            if self.controller.uart.reconnect():
                self.log("Reconnected! Retrying...")
                retry_func(*args)
            else:
                self.log("Reconnection failed.")
                self.handle_error(retry_func, *args)
        else:
            self.log("User chose to exit to menu.")
            self.exit_to_menu()
    
    def validate_response(self, cmd_sent, response, expected_size):
        if not response or response[0] != cmd_sent or len(response) != expected_size:
            return False, None
        return True, response

    def send_reset_command(self):
        self.log("CMD_RESET sent")
        self.timer_active = False 
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_RESET, 0x00):
            self.handle_error(self.send_reset_command)
            return
        
        resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
        self.controller.uart_busy = False
        
        if self.validate_response(CMD_RESET, resp, 2)[0]:
            self.log("CMD_RESET acknowledged - Waiting for board...")
            self.after(500, self.send_start_command)
        else:
            self.log("No valid response to CMD_RESET")
            self.handle_error(self.send_reset_command)

    def send_start_command(self):
        self.log("CMD_START sent - Waiting for board...")
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        layout_mode = getattr(self, 'layout_id', 0)
        if not self.controller.uart.send_packet(CMD_START, layout_mode):
            self.handle_error(self.send_start_command)
            return
        
        resp = self.controller.uart.read_packet_strictly(PACKET_SIZE, timeout_sec=10.0)
        self.controller.uart_busy = False
        
        valid, payload = self.validate_response(CMD_START, resp, 51)
        if valid:
            self.log("Board received successfully!")
            self.selected_index = None
            self.update_shuffle_counter(5)
            self.draw_pyramid(payload[1:])
            
            self.timer_active = True
            self.update_clock()
        else:
            self.log("Failed to receive valid board after CMD_START")
            self.handle_error(self.send_start_command)

    def send_shuffle_command(self):
        self.log("CMD_SHUFFLE sent")
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_SHUFFLE, 0x00):
            self.handle_error(self.send_shuffle_command)
            return

        resp = self.controller.uart.read_packet_strictly(PACKET_SIZE, timeout_sec=4.0)
        self.controller.uart_busy = False
        
        if resp and len(resp) == 51: 
            self.log("New board received after shuffle")
            self.update_shuffle_counter(self.shuffles_left - 1)
            self.selected_index = None
            self.draw_pyramid(resp[1:])
            self.check_game_over()
        else:
            if resp and len(resp) == 2 and resp[1] == 0xFF:
                self.check_game_over()
                self.log("Shuffle limit reached")
                messagebox.showwarning("Shuffle", "Limit reached!")
                self.update_shuffle_counter(0)
            else:
                self.log("Failed to receive valid response after CMD_SHUFFLE")
                self.handle_error(self.send_shuffle_command)

    def send_select_command(self, index):
        self.log(f"CMD_SELECT sent for index {index}")
        
        # Lock the door
        self.controller.uart_busy = True 
        try:
            self.controller.uart.reset_buffer()
            if self.controller.uart.send_packet(CMD_SELECT, index):
                resp = self.controller.uart.read_packet_strictly(3, timeout_sec=2.0)
                
                # Keep all your existing success/error logic here) ...
                if resp and resp[0] == CMD_SELECT:
                    if resp[1] == 0x00:
                        self.selected_index = index if self.selected_index != index else None
                        self.draw_pyramid(self.current_board_data)
                    else:
                        self.error_tiles.append(index)
                        self.draw_pyramid(self.current_board_data)
                        
                        # ---> FIX: Change clear_errors to clear_blink <---
                        self.after(500, self.clear_blink) 
                else:
                    self.handle_error(lambda: self.send_select_command(index))
            else:
                self.handle_error(lambda: self.send_select_command(index))
                
        finally:
            # Unlock the door
            self.controller.uart_busy = False

    def send_match_command(self, index):
        self.log(f"CMD_MATCH sent for index {index}")
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_MATCH, index):
            self.handle_error(self.send_match_command, index)
            return
        
        resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
        self.controller.uart_busy = False
        
        valid, payload = self.validate_response(CMD_MATCH, resp, 2)
        if valid:
            if payload[1] == 0x01: 
                temp_board = bytearray(self.current_board_data)
                temp_board[self.selected_index] = 0x00
                temp_board[index] = 0x00
                self.current_board_data = bytes(temp_board)
                self.selected_index = None
                self.draw_pyramid(self.current_board_data)
                self.check_game_over()
                if all(val == 0 for val in self.current_board_data): 
                    self.timer_active = False # Stop clock on win
                    self.after(500, lambda: self.show_end_game_popup("VICTORY!", "You cleared the board!", "#2E7D32", is_victory=True))
            else:
                old_idx = self.selected_index
                self.selected_index = None
                self.show_error_blink([old_idx, index])
        else:
            self.handle_error(self.send_match_command, index)

    def request_hint(self):
        self.log("CMD_HINT sent")
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if not self.controller.uart.send_packet(CMD_HINT, 0x00):
            self.handle_error(self.request_hint)
            return

        resp = self.controller.uart.read_packet_strictly(4, timeout_sec=1.5)
        self.controller.uart_busy = False
        
        valid, payload = self.validate_response(CMD_HINT, resp, 3)
        if valid:
            idx1, idx2 = payload[1], payload[2]
            if idx1 == 100:
                messagebox.showinfo("Hint", "No pairs left!")
            else:
                self.show_hint_blink([idx1, idx2])
        else:
            self.handle_error(self.request_hint)

    def send_giveup_command(self):
        self.timer_active = False
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if self.controller.uart.send_packet(CMD_GIVE_UP, 0x00):
            resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
            self.controller.uart_busy = False
            if resp: self.exit_to_menu()
        else:
            self.handle_error(self.send_giveup_command)

    def check_game_over(self):
        if self.shuffles_left > 0: return

        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        if self.controller.uart.send_packet(CMD_HINT, 0x00):
            resp = self.controller.uart.read_packet_strictly(4, timeout_sec=1.5)
            self.controller.uart_busy = False
            valid, payload = self.validate_response(CMD_HINT, resp, 3)
            if valid and payload[1] == 100: 
                self.timer_active = False # Stop clock on lose
                self.show_end_game_popup("GAME OVER", "No moves left & no shuffles.", "#D32F2F")

    def show_end_game_popup(self, title, message, color, is_victory=False):
        popup = tk.Toplevel(self)
        popup.title(title)
        # Make the window taller if we need to display the leaderboard
        popup.geometry("380x480" if is_victory else "300x200")
        popup.configure(bg="#f0f0f0")
        popup.grab_set()
        
        tk.Label(popup, text=title, font=("Arial", 18, "bold"), fg=color, bg="#f0f0f0").pack(pady=10)
        tk.Label(popup, text=message, font=("Arial", 10), bg="#f0f0f0").pack(pady=5)
        
        # ---> NEW: Draw Leaderboard if Victory <---
        if is_victory:
            leaders = self.fetch_leaderboard()
            if leaders:
                lb_frame = tk.Frame(popup, bg="#f0f0f0")
                lb_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)
                
                tk.Label(lb_frame, text="🏆 TOP 10 PLAYERS 🏆", font=("Arial", 12, "bold"), bg="#f0f0f0", fg="#FFA000").pack(pady=(0, 5))
                
                # Create a Treeview table
                columns = ("rank", "name", "time")
                tree = ttk.Treeview(lb_frame, columns=columns, show="headings", height=10)
                tree.heading("rank", text="#")
                tree.heading("name", text="Player Name")
                tree.heading("time", text="Time (s)")
                
                tree.column("rank", width=30, anchor="center")
                tree.column("name", width=150, anchor="w")
                tree.column("time", width=80, anchor="center")
                tree.pack(fill=tk.BOTH, expand=True)
                
                # Populate the table
                for i, (name, p_time) in enumerate(leaders):
                    display_time = f"{p_time} s" if p_time < 999999 else "---"
                    disp_name = name if name and name != "---" else "Empty Slot"
                    tree.insert("", "end", values=(i+1, disp_name, display_time))
            else:
                tk.Label(popup, text="Failed to load leaderboard.", fg="red", bg="#f0f0f0").pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(popup, bg="#f0f0f0")
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Retry", width=10, bg="#4CAF50", fg="white",
                  command=lambda: [popup.destroy(), self.send_reset_command()]).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Menu", width=10, bg="#607D8B", fg="white",
                  command=lambda: [popup.destroy(), self.exit_to_menu()]).pack(side=tk.LEFT, padx=5)
        
    def update_clock(self):
        if not self.timer_active:
            return 
            
        #Lock: If UART is busy drawing the board or clicking tiles, skip this second.
        if not self.controller.uart_busy:
            elapsed_seconds = self.controller.get_timer_from_stm32()
            
            if elapsed_seconds is not None:
                mins = elapsed_seconds // 60
                secs = elapsed_seconds % 60
                self.timer_label.config(text=f"Time: {mins:02d}:{secs:02d}")
        
        self.after(1000, self.update_clock)

    def update_shuffle_counter(self, count):
        self.shuffles_left = max(0, count)
        self.lbl_shuffles.config(text=f"Attempts: {self.shuffles_left}", fg="red" if self.shuffles_left == 0 else "black")
        self.btn_shuffle.config(state="disabled" if self.shuffles_left == 0 else "normal")

    def on_canvas_click(self, event):
        if not self.current_board_data or self.controller.uart_busy:
            return # Ignore clicks if the line is busy!
            
        clicked_idx = -1
        for hb in reversed(self.hitboxes):
            x1, y1, x2, y2, idx = hb
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                clicked_idx = idx; break
        if clicked_idx == -1: return
        
        if self.selected_index is None:
            self.send_select_command(clicked_idx)
        elif clicked_idx == self.selected_index:
            self.selected_index = None
            self.draw_pyramid(self.current_board_data)
        else:
            self.send_match_command(clicked_idx)

    def show_error_blink(self, indices):
        self.error_tiles = indices
        self.draw_pyramid(self.current_board_data)
        self.after(400, self.clear_blink)

    def clear_blink(self):
        self.error_tiles = []
        if self.current_board_data: self.draw_pyramid(self.current_board_data)

    def show_hint_blink(self, indices):
        self.hint_tiles = indices
        self.draw_pyramid(self.current_board_data)
        self.after(1500, self.clear_hint_blink)

    def clear_hint_blink(self):
        self.hint_tiles = []
        if self.current_board_data: self.draw_pyramid(self.current_board_data)

    def draw_pyramid(self, data):
        self.canvas.delete("all")
        self.hitboxes = []
        self.current_board_data = data
        self.update_idletasks()
        cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
        
        def draw_tile(idx, gx, gy, z, ox, oy):
            if idx >= len(data) or data[idx] == 0: return
            val_byte = data[idx]
            gid, val = (val_byte >> 5) & 0x07, val_byte & 0x1F
            name, color = TILE_GROUPS.get(gid, ("?", "white"))
            
            x = start_x + (gx + ox) * TILE_W - (z * SHADOW_OFFSET)
            y = start_y + (gy + oy) * TILE_H - (z * SHADOW_OFFSET)
            self.hitboxes.append((x, y, x+TILE_W, y+TILE_H, idx))

            border, b_w = ("black", 1)
            if idx == self.selected_index: border, b_w = "cyan", 3
            if idx in self.error_tiles: border, b_w = "red", 3
            if idx in self.hint_tiles: border, b_w = "yellow", 4

            self.canvas.create_rectangle(x+4, y+4, x+TILE_W+4, y+TILE_H+4, fill="#1a1a1a", outline="")
            self.canvas.create_rectangle(x, y, x+TILE_W, y+TILE_H, fill="#f0f0f0", outline=border, width=b_w)
            self.canvas.create_rectangle(x+2, y+2, x+TILE_W-2, y+TILE_H-2, fill=color, outline="")
            self.canvas.create_text(x+TILE_W/2, y+TILE_H/2-5, text=str(val), font=("Arial", 14, "bold"))
            self.canvas.create_text(x+TILE_W/2, y+TILE_H-10, text=name[:3], font=("Arial", 7))

        i = 0
        layout_mode = getattr(self, 'layout_id', 0)
        
        if layout_mode == 0:
            # Default Square Layout
            start_x, start_y = cx - (2.5 * TILE_W), cy - (2.5 * TILE_H)
            for r in range(5):
                for c in range(5): draw_tile(i, c, r, 0, 0, 0); i += 1
            for r in range(4):
                for c in range(4): draw_tile(i, c, r, 1, 0.5, 0.5); i += 1
            for r in range(3):
                for c in range(3): draw_tile(i, c, r, 2, 1, 1); i += 1
        else:
            # Symmetrical Triangle Pyramid Layout
            start_x = cx - (TILE_W / 2.0)  # Perfectly center the peak
            start_y = cy - (3.5 * TILE_H)  # Perfectly vertically center the 7 rows
            
            for layer in range(4):
                num_rows = 7 - (2 * layer)
                for row in range(num_rows):
                    num_cols = row + 1
                    for col in range(num_cols):
                        if i >= 50: break
                        
                        # Use the exact math from your test_pyramid.py!
                        x_offset = col - (row / 2.0)
                        y_offset = layer + row
                        
                        # Pass x_offset to gx, y_offset to gy, layer to z, and 0 to ox/oy
                        draw_tile(i, x_offset, y_offset, layer, 0, 0)
                        i += 1

    def fetch_leaderboard(self):
        self.log("Fetching leaderboard from STM32...")
        self.controller.uart_busy = True
        self.controller.uart.reset_buffer()
        
        # Send the request
        if not self.controller.uart.send_packet(CMD_GET_LEADERS, 0x00):
            self.controller.uart_busy = False
            return None
            
        # Read the 202-byte response (1 CMD + 200 DATA + 1 CRC)
        resp = self.controller.uart.read_packet_strictly(202, timeout_sec=2.0)
        self.controller.uart_busy = False
        
        if resp and len(resp) == 201 and resp[0] == CMD_GET_LEADERS:
            payload = resp[1:] # Strip the CMD byte
            leaders = []
            
            for i in range(10):
                chunk = payload[i*20 : (i+1)*20]
                # Unpack: 16-byte string (16s) and 4-byte unsigned int (I)
                name_raw, play_time = struct.unpack('<16sI', chunk)
                name = name_raw.decode('utf-8', errors='ignore').strip('\x00')
                leaders.append((name, play_time))
                
            return leaders
            
        self.log("Failed to receive or parse leaderboard packet.")
        return None

# --- APP CONTROLLER ---
class MahjongApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong")
        self.geometry("900x750")
        self.uart = UARTHandler()
        self.uart_busy = False # UART Lock to prevent ghost packets
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
        self.after(1000, self.game_view.send_reset_command)

    def get_timer_from_stm32(self):
        if not self.uart.is_connected():
            return None
            
        self.uart_busy = True # Lock UART while checking time
        self.uart.reset_buffer()
        
        if self.uart.send_packet(CMD_GET_TIME, 0x00):
            raw_response = self.uart.read_packet_strictly(52, timeout_sec=0.5)
            self.uart_busy = False # Release Lock
            
            if raw_response and len(raw_response) == 51: 
                if raw_response[0] == CMD_GET_TIME:
                    time_bytes = raw_response[1:5]
                    seconds = int.from_bytes(time_bytes, byteorder='big')
                    return seconds
                    
        self.uart_busy = False # Release Lock on fail
        return None
    
if __name__ == "__main__":
    app = MahjongApp()
    app.mainloop()