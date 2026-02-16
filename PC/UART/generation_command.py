import serial
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'  # Update this!
BAUD_RATE = 115200

# Tile Definitions for Visualization
GROUPS = {
    0: ("Bamboo", "forestgreen"),
    1: ("Chars",  "firebrick"),
    2: ("Circles","royalblue"),
    3: ("Winds",  "gray"),
    4: ("Dragons","gold"),
    5: ("Flowers","orchid"),
    6: ("Seasons","orange")
}

def parse_tile(byte):
    group_id = (byte >> 5) & 0x07
    value = byte & 0x1F
    return group_id, value

def get_mahjong_data():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        print(f"Connected to {SERIAL_PORT}...")
        
        # Reset DTR to restart board (optional, helps with syncing)
        ser.dtr = False; time.sleep(0.1); ser.dtr = True; time.sleep(1.0)
        ser.reset_input_buffer()

        # Send CMD: 0x01 (Start) | 0x00 (Data) | 0x01 (CRC)
        print("Sending Start Command...")
        ser.write(bytes([0x01, 0x00, 0x01]))

        # Expect 52 bytes (1 CMD + 50 DATA + 1 CRC)
        response = ser.read(52)
        ser.close()

        if len(response) != 52:
            print(f"Error: Received {len(response)} bytes. Check connections.")
            return None

        # Extract only the 50 data bytes
        raw_data = response[1:51]
        print("Data Received Successfully!")
        return raw_data

    except Exception as e:
        print(f"Serial Error: {e}")
        return None

def visualize_layout(data):
    # Slice the flat 50-byte array into layers
    # Layer 1: 5x5 (25 tiles)
    l1 = [parse_tile(b) for b in data[0:25]]
    # Layer 2: 4x4 (16 tiles)
    l2 = [parse_tile(b) for b in data[25:41]]
    # Layer 3: 3x3 (9 tiles)
    l3 = [parse_tile(b) for b in data[41:50]]

    layers = [
        (l1, 5, "Layer 1 (Bottom)"),
        (l2, 4, "Layer 2 (Middle)"),
        (l3, 3, "Layer 3 (Top)")
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, (layer_data, size, title) in zip(axes, layers):
        # Create a grid for colors and texts
        grid_colors = np.zeros((size, size, 3)) # RGB
        
        for i, (grp, val) in enumerate(layer_data):
            row, col = divmod(i, size)
            
            # Get color and name
            name, color_name = GROUPS.get(grp, ("Unknown", "black"))
            
            # Draw the text (Value)
            ax.text(col, row, f"{val}", ha='center', va='center', 
                    color='white', fontsize=12, fontweight='bold',
                    bbox=dict(facecolor=color_name, edgecolor='black', boxstyle='round,pad=0.5'))
            
            # Add small label for group
            ax.text(col, row+0.3, name[:3], ha='center', va='center', 
                    color='black', fontsize=8)

        # Configure Grid
        ax.set_title(title)
        ax.set_xticks(np.arange(size) - 0.5)
        ax.set_yticks(np.arange(size) - 0.5)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.grid(which="major", color="black", linestyle='-', linewidth=2)
        ax.set_xlim(-0.5, size - 0.5)
        ax.set_ylim(size - 0.5, -0.5) # Invert Y so 0,0 is top-left

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    data = get_mahjong_data()
    if data:
        visualize_layout(data)