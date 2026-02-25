import tkinter as tk
from tkinter import ttk, messagebox
import time
from UART_handler import UARTHandler

# --- КОНФІГУРАЦІЯ ---
CMD_START = 0x01
CMD_RESET = 0x02
CMD_SHUFFLE = 0x03
CMD_SELECT = 0x04
CMD_MATCH = 0x05
CMD_GIVE_UP = 0x07
CMD_HINT = 0x08
PACKET_SIZE = 52  # 50 тайлів + 1 байт CMD + 1 байт CRC
TILE_W, TILE_H, SHADOW_OFFSET = 50, 65, 4

TILE_GROUPS = {
    0: ("Bamboo", "#66BB6A"), 1: ("Chars", "#EF5350"), 2: ("Circles", "#42A5F5"),
    3: ("Winds", "#BDBDBD"), 4: ("Dragons", "#FFEE58"), 5: ("Flowers", "#AB47BC"), 6: ("Seasons", "#FFA726")
}

# --- ГОЛОВНЕ МЕНЮ ---
class MainMenu(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f0f0")
        self.controller = controller
        
        tk.Label(self, text="STM32 Mahjong", font=("Arial", 28, "bold"), bg="#f0f0f0").pack(pady=(100, 10))
        self.lbl_status = tk.Label(self, text="Ready", font=("Arial", 10, "italic"), bg="#f0f0f0")
        self.lbl_status.pack(pady=(0, 20))

        # Player Name Entry
        frame_name = tk.Frame(self, bg="#f0f0f0")
        frame_name.pack(pady=(10, 20))
        tk.Label(frame_name, text="Player Name: (Up to 10 characters)", font=("Arial", 12), bg="#f0f0f0").grid(row=0, column=0, padx=5)
        self.player_name_var = tk.StringVar(value="Player1")
        self.entry_name = tk.Entry(frame_name, textvariable=self.player_name_var, font=("Arial", 12), width=15)
        self.entry_name.grid(row=0, column=1, padx=5)

        frame_port = tk.Frame(self, bg="#f0f0f0")
        frame_port.pack()
        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(frame_port, textvariable=self.port_var, width=15, state="readonly")
        self.combo_ports.grid(row=0, column=0, padx=10)
        
        tk.Button(frame_port, text="↻", command=self.refresh_ports).grid(row=0, column=1)
        tk.Button(self, text="CONNECT & PLAY", command=self.connect, bg="#4CAF50", fg="white", font=("Arial", 14, "bold"), pady=10).pack(pady=40)

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def refresh_ports(self):
        ports = UARTHandler.list_available_ports()
        self.combo_ports['values'] = ports
        if ports: self.combo_ports.current(0)
        else: self.port_var.set("No Ports Found")

    def send_player_name(self, name):
        """
        PLACEHOLDER: Handle the entered name.
        You can format this into a new UART packet (e.g., CMD_SET_NAME = 0x09) 
        to send the string to the STM32, or just save it locally for a leaderboard.
        """
        self.log(f"Registered player name: {name}")
        
        # Example for future UART implementation (requires updating UARTHandler to send variable length arrays):
        # byte_name = name.encode('ascii')[:10] # Limit to 10 chars
        # self.controller.uart.send_packet(CMD_SET_NAME, byte_name)

    def connect(self):
        self.log("Attempting to connect...")
        port = self.port_var.get()
        if not port or port == "No Ports Found": 
            self.log("No port selected or available.")
            return
        self.controller.uart.port_name = port
        if self.controller.uart.open_port():
            self.log(f"Connected to {port}")
            self.controller.uart.dtr_reset()
            self.controller.show_game()
        else:
            self.log(f"Failed to connect to {port}")
            messagebox.showerror("Error", "Could not open port!")

# --- ІНТЕРФЕЙС ГРИ ---
class GameInterface(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.current_board_data = None
        self.hitboxes = []
        self.selected_index = None
        self.error_tiles = []
        self.shuffles_left = 5
        self.hint_tiles = []

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
        self.controller.uart.close_port()
        self.controller.show_menu()

    def handle_error(self, retry_func, *args):
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
        self.log(f"Received response: {response}")
        if not response:
            return False, None
        if response[0] != cmd_sent:
            return False, None
        if len(response) != expected_size:
            return False, None
        return True, response

    # --- КОМАНДИ З ТАЙМАУТАМИ ---
    def send_reset_command(self):
        self.log("CMD_RESET sent")
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_RESET, 0x00):
            self.log("Failed to send CMD_RESET")
            self.handle_error(self.send_reset_command)
            return
        
        resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
        if self.validate_response(CMD_RESET, resp, 2)[0]:
            self.log("CMD_RESET acknowledged - Waiting for board...")
            self.after(500, self.send_start_command)
        else:
            self.log("No valid response to CMD_RESET")
            self.handle_error(self.send_reset_command)

    def send_start_command(self):
        self.log("CMD_START sent - Waiting for board...")
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_START, 0x00):
            self.log("Failed to send CMD_START")
            self.handle_error(self.send_start_command)
            return
        
        # Чекаємо 5 секунд на генерацію
        resp = self.controller.uart.read_packet_strictly(PACKET_SIZE, timeout_sec=10.0)
        valid, payload = self.validate_response(CMD_START, resp, 51)
        if valid:
            self.log("Board received successfully!")
            self.selected_index = None
            self.update_shuffle_counter(5)
            self.draw_pyramid(payload[1:])
        else:
            self.log("Failed to receive valid board after CMD_START")
            self.handle_error(self.send_start_command)

    def send_shuffle_command(self):
        self.log("CMD_SHUFFLE sent")
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_SHUFFLE, 0x00):
            self.log("Failed to send CMD_SHUFFLE")
            self.handle_error(self.send_shuffle_command)
            return

        # Спочатку намагаємося прочитати як повну дошку (52 байти)
        resp = self.controller.uart.read_packet_strictly(PACKET_SIZE, timeout_sec=4.0)
        
        if resp and len(resp) == 51: # Успіх
            self.log("New board received after shuffle")
            self.update_shuffle_counter(self.shuffles_left - 1)
            self.selected_index = None
            self.draw_pyramid(resp[1:])
            self.check_game_over()
        else:
            # Якщо дошка не прийшла, можливо це помилка ліміту (0xFF)
            # Перевіримо буфер на 3-байтову відповідь
            self.log("No full board received, checking for shuffle limit response...")
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
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_SELECT, index):
            self.log("Failed to send CMD_SELECT")
            self.handle_error(self.send_select_command, index)
            return
        
        resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
        valid, payload = self.validate_response(CMD_SELECT, resp, 2)
        if valid:
            self.log(f"CMD_SELECT response: {payload[1]}")
            if payload[1] == 0x00:
                self.log(f"Tile at index {index} is selectable")
                self.selected_index = index
                self.draw_pyramid(self.current_board_data)
            else:
                self.log(f"Tile at index {index} is NOT selectable")
                self.show_error_blink([index])
        else:
            self.log("Failed to receive valid response after CMD_SELECT")
            self.handle_error(self.send_select_command, index)

    def send_match_command(self, index):
        self.log(f"CMD_MATCH sent for index {index} with selected index {self.selected_index}")
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_MATCH, index):
            self.log("Failed to send CMD_MATCH")
            self.handle_error(self.send_match_command, index)
            return
        
        resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
        valid, payload = self.validate_response(CMD_MATCH, resp, 2)
        if valid:
            self.log(f"CMD_MATCH response: {payload[1]}")
            if payload[1] == 0x01: # Match
                self.log(f"Tiles at indices {self.selected_index} and {index} matched and removed")
                temp_board = bytearray(self.current_board_data)
                temp_board[self.selected_index] = 0x00
                temp_board[index] = 0x00
                self.current_board_data = bytes(temp_board)
                self.selected_index = None
                self.draw_pyramid(self.current_board_data)
                self.check_game_over()
                if all(val == 0 for val in self.current_board_data): #я
                    self.after(500, lambda: self.show_end_game_popup("VICTORY!", "You cleared the board!", "#2E7D32"))
            else:
                self.log(f"Tiles at indices {self.selected_index} and {index} do NOT match")
                old_idx = self.selected_index
                self.selected_index = None
                self.show_error_blink([old_idx, index])
        else:
            self.log("Failed to receive valid response after CMD_MATCH")
            self.handle_error(self.send_match_command, index)

    def request_hint(self):
        self.log("CMD_HINT sent")
        self.controller.uart.reset_buffer()
        if not self.controller.uart.send_packet(CMD_HINT, 0x00):
            self.log("Failed to send CMD_HINT")
            self.handle_error(self.request_hint)
            return

        resp = self.controller.uart.read_packet_strictly(4, timeout_sec=1.5)
        valid, payload = self.validate_response(CMD_HINT, resp, 3)
        if valid:
            self.log(f"CMD_HINT response: {payload[1]}, {payload[2]}")
            idx1, idx2 = payload[1], payload[2]
            if idx1 == 100:
                self.log("No pairs left for hint")
                messagebox.showinfo("Hint", "No pairs left!")
            else:
                self.log(f"Indices available {idx1} and {idx2}")
                self.show_hint_blink([idx1, idx2])
        else:
            self.log("Failed to receive valid response after CMD_HINT")
            self.handle_error(self.request_hint)

    def send_giveup_command(self):
        self.log("CMD_GIVE_UP sent")
        self.controller.uart.reset_buffer()
        if self.controller.uart.send_packet(CMD_GIVE_UP, 0x00):
            self.log("CMD_GIVE_UP sent successfully, waiting for response...")
            resp = self.controller.uart.read_packet_strictly(3, timeout_sec=1.0)
            if resp: self.exit_to_menu()
        else:
            self.log("Failed to send CMD_GIVE_UP")
            self.handle_error(self.send_giveup_command)

    def check_game_over(self):
        # Якщо є спроби перемішування - гра продовжується
        if self.shuffles_left > 0:
            return

        # Якщо спроб немає, запитуємо STM32, чи є ще ходи (викликаємо CMD_HINT)
        self.controller.uart.reset_buffer()
        if self.controller.uart.send_packet(CMD_HINT, 0x00):
            resp = self.controller.uart.read_packet_strictly(4, timeout_sec=1.5)
            valid, payload = self.validate_response(CMD_HINT, resp, 3)
            if valid and payload[1] == 100: # 100 означає "No pairs left" в твоєму С-коді
                self.show_end_game_popup("GAME OVER", "No moves left & no shuffles.", "#D32F2F")

    # final screen of win/lose
    def show_end_game_popup(self, title, message, color):
        # Створюємо нове вікно поверх основного
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("300x200")
        popup.configure(bg="#f0f0f0")
        
        # Робимо його модальним (блокуємо основне вікно)
        popup.grab_set()
        
        # Текст повідомлення
        tk.Label(popup, text=title, font=("Arial", 18, "bold"), fg=color, bg="#f0f0f0").pack(pady=10)
        tk.Label(popup, text=message, font=("Arial", 10), bg="#f0f0f0").pack(pady=5)
        
        btn_frame = tk.Frame(popup, bg="#f0f0f0")
        btn_frame.pack(pady=20)
        
        # Кнопка "Спробувати знову"
        tk.Button(btn_frame, text="Retry", width=10, bg="#4CAF50", fg="white",
                  command=lambda: [popup.destroy(), self.send_reset_command()]).pack(side=tk.LEFT, padx=5)
        
        # Кнопка "В меню"
        tk.Button(btn_frame, text="Menu", width=10, bg="#607D8B", fg="white",
                  command=lambda: [popup.destroy(), self.exit_to_menu()]).pack(side=tk.LEFT, padx=5)

    # --- ВІЗУАЛІЗАЦІЯ (БЕЗ ЗМІН) ---
    def update_shuffle_counter(self, count):
        self.shuffles_left = max(0, count)
        self.lbl_shuffles.config(text=f"Attempts: {self.shuffles_left}", fg="red" if self.shuffles_left == 0 else "black")
        self.btn_shuffle.config(state="disabled" if self.shuffles_left == 0 else "normal")

    def on_canvas_click(self, event):
        self.log(f"Canvas clicked at ({event.x}, {event.y})")
        if not self.current_board_data:
            self.log("No board data available")
            return
        clicked_idx = -1
        for hb in reversed(self.hitboxes):
            x1, y1, x2, y2, idx = hb
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                clicked_idx = idx; break
        if clicked_idx == -1: return
        
        if self.selected_index is None:
            self.log(f"Tile at index {clicked_idx} clicked - sending select command")
            self.send_select_command(clicked_idx)
        elif clicked_idx == self.selected_index:
            self.log(f"Tile at index {clicked_idx} deselected")
            self.selected_index = None
            self.draw_pyramid(self.current_board_data)
        else:
            self.log(f"Tile at index {clicked_idx} clicked - sending match command with selected index {self.selected_index}")
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
        start_x, start_y = cx - (2.5 * TILE_W), cy - (2.5 * TILE_H)

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
        for r in range(5):
            for c in range(5): draw_tile(i, c, r, 0, 0, 0); i += 1
        for r in range(4):
            for c in range(4): draw_tile(i, c, r, 1, 0.5, 0.5); i += 1
        for r in range(3):
            for c in range(3): draw_tile(i, c, r, 2, 1, 1); i += 1

# --- ДОДАТОК ---
class MahjongApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM32 Mahjong")
        self.geometry("900x750")
        self.uart = UARTHandler()
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

if __name__ == "__main__":
    app = MahjongApp()
    app.mainloop()