# Mahjong Solitaire – PC Environment Setup

## Project Overview
This repository contains the Python-based User Interface (UI) for the Mahjong Solitaire project. The application is designed to function as a visual terminal that communicates with an **STM32 microcontroller** via UART protocol. 

While the core game logic and pair checking are intended to be processed on the STM32 side, this PC client handles tile rendering, user inputs, and visual feedback.

## Features
* **Dual Mode Support**: Includes a "Test Mode" for standalone UI demonstration and a "Full Mode" for active UART communication.
* [cite_start]**Optimized Layout**: A symmetrical 60-tile pyramid structure (30 pairs) arranged in 2 layers for clear visibility[cite: 23, 6].
* **Game Controls**: Fully functional buttons for **Hint**, **Shuffle**, **Restart**, and **Exit**.
* **Real-time Communication**: Multi-threaded UART listener to process commands from the STM32 without UI freezing.

## Requirements
* **Python 3.10+**
* **pyserial** library (for UART communication)
* **tkinter** library (standard Python GUI toolkit)

## Installation
To install the necessary dependencies, run the following command:
```bash
pip install pyserial