import tkinter as tk      # бібліотека для створення вікна (UI)
import serial             # pyserial, для UART

root = tk.Tk()            # створюю головне вікно
root.title("Mahjong UART UI")  # назва вікна
root.geometry("600x400")  # розмір вікна

label = tk.Label(
    root,
    text="Mahjong UI is running",
    font=("Arial", 14)
)
label.pack(pady=40)       # показує текст з відступом

root.mainloop()           # запуска. програму
