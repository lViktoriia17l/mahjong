import tkinter as tk
from tkinter import messagebox, ttk
import random
import threading
import time
import struct

try:
    import serial
except ImportError:
    serial = None

# --- КОНСТАНТИ ПРОТОКОЛУ ---
CMD_START = 0x01
CMD_RESET = 0x02
CMD_SHUFFLE = 0x03
CMD_SELECT = 0x04
CMD_MATCH = 0x05
CMD_GET_STATE = 0x06


class MahjongGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Mahjong Solitaire Prototype")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1a1a1a")

        self.selected_tile = None
        self.first_click_encoded = None
        self.tiles_dict = {}
        self.ser = None
        self.is_test_mode = True

        self.base_symbols = (
                ["🀀", "🀁", "🀂", "🀃", "🀄", "🀅", "🀆", "🀇", "🀈", "🀉",
                 "🀊", "🀋", "🀌", "🀍", "🀎", "🀏", "🀐", "🀑", "🀒", "🀓",
                 "🀔", "🀕", "🀖", "🀗", "🀘", "🀙", "🀚", "🀛"] * 2 +
                ["🌸", "🍂", "🌿", "❄️"]
        )
        self.tile_symbols = self.base_symbols[:60]

        self.setup_main_menu()

    def calculate_crc(self, cmd, data):
        return cmd ^ data

    def send_packet(self, cmd, data):
        if self.ser and self.ser.is_open:
            crc = self.calculate_crc(cmd, data)
            packet = struct.pack('BBB', cmd, data, crc)
            self.ser.write(packet)
            print(f"UART Sent -> CMD:{hex(cmd)} DATA:{hex(data)} CRC:{hex(crc)}")

    def encode_coords(self, x, y, z):
        return (y & 0x07) | ((x & 0x07) << 3) | ((z & 0x03) << 6)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def setup_main_menu(self):
        self.clear_screen()
        frame = tk.Frame(self.root, bg="#2d2d2d", padx=50, pady=50, highlightthickness=2, highlightbackground="#4a4a4a")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="MAHJONG PROJECT", font=("Helvetica", 24, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(
            pady=20)

        tk.Label(frame, text="Select COM Port:", fg="#aaaaaa", bg="#2d2d2d").pack()
        self.port_var = tk.StringVar(value="COM3")
        available_ports = ["COM1", "COM2", "COM3", "COM4", "/dev/ttyUSB0"]
        port_menu = ttk.Combobox(frame, textvariable=self.port_var, values=available_ports)
        port_menu.pack(pady=10)

        btn_s = {"font": ("Helvetica", 12), "width": 25, "pady": 10, "cursor": "hand2", "fg": "white"}

        tk.Button(frame, text="Start Test Mode (No UART)", bg="#4CAF50",
                  command=lambda: self.start_game(True), **btn_s).pack(pady=5)

        tk.Button(frame, text="Start Full Mode (UART)", bg="#2196F3",
                  command=lambda: self.start_game(False), **btn_s).pack(pady=5)

    def start_game(self, mode):
        self.is_test_mode = mode
        if not self.is_test_mode:
            if serial is None:
                messagebox.showerror("Error", "pyserial library not found!")
                return
            try:
                # ЗМІНА 1: Швидкість 115200 замість 9600
                self.ser = serial.Serial(self.port_var.get(), 115200, timeout=0.1)

                # ЗМІНА 2: Пустий байт тепер 0x00, як у тесті колеги
                self.send_packet(CMD_START, 0x00)

                threading.Thread(target=self.listen_to_stm, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not open {self.port_var.get()}:\n{e}")
                return

        self.setup_game_interface()

    def listen_to_stm(self):
        while self.ser and self.ser.is_open:
            if self.ser.in_waiting > 0:
                try:
                    cmd_byte = self.ser.read(1)
                    if not cmd_byte: continue
                    cmd = struct.unpack('B', cmd_byte)[0]

                    bytes_to_read = 2
                    if cmd in [CMD_START, CMD_RESET, CMD_SHUFFLE]:
                        bytes_to_read = 51
                    elif cmd == CMD_MATCH:
                        bytes_to_read = 52

                    payload = self.ser.read(bytes_to_read)

                    if len(payload) == bytes_to_read:
                        print(f"UART Recv <- CMD:{hex(cmd)} Len:{len(payload)}")
                except Exception as e:
                    print(f"UART Error: {e}")
            time.sleep(0.01)

    def setup_game_interface(self):
        self.clear_screen()
        top = tk.Frame(self.root, bg="#333", height=60)
        top.pack(side="top", fill="x")

        cfg = {"bg": "#444", "fg": "white", "font": ("Arial", 10, "bold"), "relief": "flat", "padx": 15,
               "cursor": "hand2"}

        tk.Button(top, text="HINT", command=lambda: self.handle_protocol_btn(CMD_GET_STATE), **cfg).pack(side="left",
                                                                                                         padx=10,
                                                                                                         pady=10)
        tk.Button(top, text="SHUFFLE", command=lambda: self.handle_protocol_btn(CMD_SHUFFLE), **cfg).pack(side="left",
                                                                                                          padx=10,
                                                                                                          pady=10)
        tk.Button(top, text="RESTART", command=lambda: self.handle_protocol_btn(CMD_RESET), **cfg).pack(side="left",
                                                                                                        padx=10,
                                                                                                        pady=10)
        tk.Button(top, text="EXIT TO MENU", command=self.exit_to_menu, bg="#d32f2f", fg="white", relief="flat").pack(
            side="right", padx=10, pady=10)

        self.canvas = tk.Canvas(self.root, bg="#143d14", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.root.after(100, self.spawn_tiles)

    def handle_protocol_btn(self, cmd):
        if not self.is_test_mode:
            self.send_packet(cmd, 0x00)  # Відправляємо 0x00 замість 0xFF
        else:
            if cmd == CMD_SHUFFLE: self.shuffle_action()
            if cmd == CMD_RESET: self.setup_game_interface()
            if cmd == CMD_GET_STATE: self.show_hint()

    def spawn_tiles(self):
        self.tiles_dict = {}
        self.canvas.delete("all")
        self.selected_tile = None
        self.first_click_encoded = None

        c_w, c_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        active_symbols = list(self.tile_symbols[:50])
        random.shuffle(active_symbols)

        t_w, t_h = 60, 80
        gap = 2
        id_counter = 0

        layers_config = [(5, 5, 0), (4, 4, 1), (3, 3, 2)]

        for cols, rows, z in layers_config:
            layer_w = cols * t_w + (cols - 1) * gap
            layer_h = rows * t_h + (rows - 1) * gap
            start_x = (c_w - layer_w) // 2
            start_y = (c_h - layer_h) // 2
            layer_offset = z * 5

            for i in range(cols * rows):
                r, c = divmod(i, cols)
                x = start_x + c * (t_w + gap) - layer_offset
                y = start_y + r * (t_h + gap) - layer_offset

                self.create_tile_obj(x, y, active_symbols.pop(), z, id_counter, c, r)
                id_counter += 1

    def create_tile_obj(self, x, y, sym, layer, t_id, gx, gy):
        off = 4 if layer == 0 else 8
        shadow = self.canvas.create_rectangle(x + off, y + off, x + 65 + off, y + 85 + off, fill="#0b240b", outline="")
        f_col = "#fdf5e6" if layer == 0 else "#ffffff"
        rect = self.canvas.create_rectangle(x, y, x + 65, y + 85, fill=f_col, outline="#8b4513", width=2)
        text = self.canvas.create_text(x + 32, y + 42, text=sym, font=("Arial", 22, "bold"))

        tile = {
            "rect": rect, "text": text, "shadow": shadow, "sym": sym,
            "layer": layer, "x": x, "y": y, "id": t_id,
            "gx": gx, "gy": gy
        }
        self.tiles_dict[t_id] = tile
        for item in (rect, text):
            self.canvas.tag_bind(item, "<Button-1>", lambda e, t=tile: self.on_click(t))

    def on_click(self, tile):
        if not self.is_test_mode:
            encoded = self.encode_coords(tile['gx'], tile['gy'], tile['layer'])

            if self.first_click_encoded is None:
                print("First Click: Sending SELECT")
                self.send_packet(CMD_SELECT, encoded)
                self.first_click_encoded = encoded
                self.selected_tile = tile
                self.canvas.itemconfig(tile["rect"], fill="#add8e6")
            else:
                print("Second Click: Sending MATCH")
                self.send_packet(CMD_MATCH, encoded)
                self.first_click_encoded = None
                if self.selected_tile:
                    self.canvas.itemconfig(self.selected_tile["rect"],
                                           fill="#ffffff" if self.selected_tile["layer"] == 1 else "#fdf5e6")
                self.selected_tile = None

            return

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

    def shuffle_action(self):
        syms = [t["sym"] for t in self.tiles_dict.values()]
        random.shuffle(syms)
        for i, (t_id, t) in enumerate(self.tiles_dict.items()):
            t["sym"] = syms[i]
            self.canvas.itemconfig(t["text"], text=t["sym"])

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

    def exit_to_menu(self):
        if self.ser:
            self.ser.close()
            self.ser = None
        self.setup_main_menu()


if __name__ == "__main__":
    root = tk.Tk()
    app = MahjongGame(root)
    root.mainloop()