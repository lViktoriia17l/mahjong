import tkinter as tk
from tkinter import messagebox, ttk
import random
import threading
import time

# Спробуємо імпортувати serial, якщо бібліотека встановлена
try:
    import serial
except ImportError:
    serial = None


class MahjongGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Mahjong Solitaire Prototype")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1a1a1a")

        self.selected_tile = None
        self.tiles_dict = {}  # Словник для швидкого доступу за ID: {id: tile_data}
        self.ser = None
        self.is_test_mode = True

        # Набір для 60 тайлів (30 пар) для ідеальної симетрії
        self.base_symbols = (
                ["🀀", "🀁", "🀂", "🀃", "🀄", "🀅", "🀆", "🀇", "🀈", "🀉",
                 "🀊", "🀋", "🀌", "🀍", "🀎", "🀏", "🀐", "🀑", "🀒", "🀓",
                 "🀔", "🀕", "🀖", "🀗", "🀘", "🀙", "🀚", "🀛"] * 2 +
                ["🌸", "🍂", "🌿", "❄️"]  # Спеціальні тайли (квіти/сезони)
        )
        self.tile_symbols = self.base_symbols[:60]

        self.setup_main_menu()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def setup_main_menu(self):
        """Start Page: Menu (choose COM Port, connection, start button)"""
        self.clear_screen()
        frame = tk.Frame(self.root, bg="#2d2d2d", padx=50, pady=50, highlightthickness=2, highlightbackground="#4a4a4a")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="MAHJONG PROJECT", font=("Helvetica", 24, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(
            pady=20)

        # Вибір COM-порту
        tk.Label(frame, text="Select COM Port:", fg="#aaaaaa", bg="#2d2d2d").pack()
        self.port_var = tk.StringVar(value="COM1")
        available_ports = ["COM1", "COM2", "COM3", "COM4", "/dev/ttyUSB0"]
        port_menu = ttk.Combobox(frame, textvariable=self.port_var, values=available_ports)
        port_menu.pack(pady=10)

        btn_s = {"font": ("Helvetica", 12), "width": 25, "pady": 10, "cursor": "hand2", "fg": "white"}

        # Кнопка тестового режиму
        tk.Button(frame, text="Start Test Mode (No UART)", bg="#4CAF50",
                  command=lambda: self.start_game(True), **btn_s).pack(pady=5)

        # Кнопка повного режиму
        tk.Button(frame, text="Start Full Mode (UART)", bg="#2196F3",
                  command=lambda: self.start_game(False), **btn_s).pack(pady=5)

    def start_game(self, mode):
        self.is_test_mode = mode
        if not self.is_test_mode:
            if serial is None:
                messagebox.showerror("Error", "pyserial library not found! Install it via 'pip install pyserial'.")
                return
            try:
                # Налаштування UART драйвера
                self.ser = serial.Serial(self.port_var.get(), 9600, timeout=0.1)
                # Потік для прослуховування команд від STM32
                threading.Thread(target=self.listen_to_stm, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not open {self.port_var.get()}:\n{e}")
                return

        self.setup_game_interface()

    def listen_to_stm(self):
        """Очікування команд від STM32 через UART"""
        while self.ser and self.ser.is_open:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    self.process_stm_command(line)
                except:
                    pass
            time.sleep(0.01)

    def process_stm_command(self, command):
        """Обробка вхідних пакетів (наприклад, 'REMOVE:5' або 'HINT:10')"""
        try:
            cmd, val = command.split(':')
            t_id = int(val)
            if cmd == "REMOVE" and t_id in self.tiles_dict:
                self.root.after(0, lambda: self.remove_tile(self.tiles_dict[t_id]))
            elif cmd == "HINT" and t_id in self.tiles_dict:
                self.root.after(0, lambda: self.canvas.itemconfig(self.tiles_dict[t_id]["rect"], fill="#ffff00"))
        except:
            pass

    def setup_game_interface(self):
        """Game Page: mahjong layout, reset, hint button"""
        self.clear_screen()
        top = tk.Frame(self.root, bg="#333", height=60)
        top.pack(side="top", fill="x")

        cfg = {"bg": "#444", "fg": "white", "font": ("Arial", 10, "bold"), "relief": "flat", "padx": 15,
               "cursor": "hand2"}
        tk.Button(top, text="HINT", command=self.handle_hint_click, **cfg).pack(side="left", padx=10, pady=10)
        tk.Button(top, text="SHUFFLE", command=self.shuffle_action, **cfg).pack(side="left", padx=10, pady=10)
        tk.Button(top, text="RESTART", command=self.setup_game_interface, **cfg).pack(side="left", padx=10, pady=10)
        tk.Button(top, text="EXIT TO MENU", command=self.exit_to_menu, bg="#d32f2f", fg="white", relief="flat").pack(
            side="right", padx=10, pady=10)

        self.canvas = tk.Canvas(self.root, bg="#143d14", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.root.after(100, self.spawn_tiles)

    def spawn_tiles(self):
        self.tiles_dict = {}
        self.canvas.delete("all")
        self.selected_tile = None

        c_w, c_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        syms = list(self.tile_symbols)
        random.shuffle(syms)

        t_w, t_h = 65, 85
        gap = 2
        id_counter = 0

        # --- ШАР 0: Прямокутник 8x6 (48 тайлів) ---
        c0, r0 = 8, 6
        s_x0 = (c_w - (c0 * t_w + (c0 - 1) * gap)) // 2
        s_y0 = (c_h - (r0 * t_h + (r0 - 1) * gap)) // 2

        for i in range(48):
            r, c = divmod(i, c0)
            self.create_tile_obj(s_x0 + c * (t_w + gap), s_y0 + r * (t_h + gap), syms.pop(), 0, id_counter)
            id_counter += 1

        # --- ШАР 1: Центрований 4x3 (12 тайлів) ---
        c1, r1 = 4, 3
        s_x1 = (c_w - (c1 * t_w + (c1 - 1) * gap)) // 2
        s_y1 = (c_h - (r1 * t_h + (r1 - 1) * gap)) // 2

        for i in range(12):
            r, c = divmod(i, c1)
            self.create_tile_obj(s_x1 + c * (t_w + gap) - 6, s_y1 + r * (t_h + gap) - 6, syms.pop(), 1, id_counter)
            id_counter += 1

    def create_tile_obj(self, x, y, sym, layer, t_id):
        off = 4 if layer == 0 else 8
        shadow = self.canvas.create_rectangle(x + off, y + off, x + 65 + off, y + 85 + off, fill="#0b240b", outline="")
        f_col = "#fdf5e6" if layer == 0 else "#ffffff"
        rect = self.canvas.create_rectangle(x, y, x + 65, y + 85, fill=f_col, outline="#8b4513", width=2)
        text = self.canvas.create_text(x + 32, y + 42, text=sym, font=("Arial", 22, "bold"))

        tile = {"rect": rect, "text": text, "shadow": shadow, "sym": sym, "layer": layer, "x": x, "y": y, "id": t_id}
        self.tiles_dict[t_id] = tile
        for item in (rect, text):
            self.canvas.tag_bind(item, "<Button-1>", lambda e, t=tile: self.on_click(t))

    def on_click(self, tile):
        if not self.is_test_mode:
            # У повному режимі відсилаємо ID натиснутого тайла в UART для STM32
            if self.ser and self.ser.is_open:
                self.ser.write(f"SELECT:{tile['id']}\n".encode())
            return

        # Логіка для тестового режиму
        if not self.is_free(tile): return
        if self.selected_tile:
            if self.selected_tile == tile:
                self.canvas.itemconfig(tile["rect"], fill="#ffffff" if tile["layer"] == 1 else "#fdf5e6")
                self.selected_tile = None
            elif self.selected_tile["sym"] == tile["sym"] or self.is_special(self.selected_tile, tile):
                self.remove_tile(self.selected_tile)
                self.remove_tile(tile)
                self.selected_tile = None
            else:
                self.canvas.itemconfig(self.selected_tile["rect"],
                                       fill="#ffffff" if self.selected_tile["layer"] == 1 else "#fdf5e6")
                self.selected_tile = tile
                self.canvas.itemconfig(tile["rect"], fill="#add8e6")
        else:
            self.selected_tile = tile
            self.canvas.itemconfig(tile["rect"], fill="#add8e6")

    def is_free(self, tile):
        # Тайл вільний, якщо на шар вище в його координатах немає іншого тайла
        for t_id, t in self.tiles_dict.items():
            if t["layer"] > tile["layer"]:
                if abs(t["x"] - tile["x"]) < 50 and abs(t["y"] - tile["y"]) < 50:
                    return False
        return True

    def is_special(self, t1, t2):
        spec = ["🌸", "🍂", "🌿", "❄️"]
        return t1["sym"] in spec and t2["sym"] in spec

    def remove_tile(self, t):
        for i in (t["rect"], t["text"], t["shadow"]): self.canvas.delete(i)
        if t["id"] in self.tiles_dict: del self.tiles_dict[t["id"]]

    def handle_hint_click(self):
        if not self.is_test_mode and self.ser:
            self.ser.write(b"GET_HINT\n")
        else:
            self.show_hint()

    def show_hint(self):
        ids = list(self.tiles_dict.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                t1, t2 = self.tiles_dict[ids[i]], self.tiles_dict[ids[j]]
                if (t1["sym"] == t2["sym"] or self.is_special(t1, t2)) and self.is_free(t1) and self.is_free(t2):
                    self.canvas.itemconfig(t1["rect"], fill="#ffff00")
                    self.canvas.itemconfig(t2["rect"], fill="#ffff00")
                    return
        messagebox.showinfo("Hint", "No more moves!")

    def shuffle_action(self):
        if not self.is_test_mode and self.ser:
            self.ser.write(b"SHUFFLE\n")
            return

        syms = [t["sym"] for t in self.tiles_dict.values()]
        random.shuffle(syms)
        for i, (t_id, t) in enumerate(self.tiles_dict.items()):
            t["sym"] = syms[i]
            self.canvas.itemconfig(t["text"], text=t["sym"])

    def exit_to_menu(self):
        if self.ser:
            self.ser.close()
            self.ser = None
        self.setup_main_menu()


if __name__ == "__main__":
    root = tk.Tk()
    app = MahjongGame(root)
    root.mainloop()