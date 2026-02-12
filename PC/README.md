# Маджонг – Налаштування середовища ПК

## Опис
Програма Python UI для ПК.
Підготовлена для UART-комунікації з STM32.

## Вимоги
- Python 3.10+
- Бібліотека **pyserial**
- Бібліотека **tkinter**

## Запуск
```bash
python main.py


---
Prototype the UI

## Project Overview
This Python-based UI serves as the visual interface for the Mahjong Solitaire project. It is designed to communicate with an **STM32 microcontroller** via UART protocol.

## Features
* **Dual Mode Support**: Includes "Test Mode" for standalone demonstration and "Full Mode" for UART communication.
* **Optimized Layout**: A symmetrical 60-tile pyramid structure (30 pairs) arranged in 2 layers.
* **Game Controls**: Buttons for **Hint**, **Shuffle**, **Restart**, and **Exit**.

## Requirements
* **Python 3.10+**
* **pyserial** library
* **tkinter** library

## Installation
```bash
pip install pyserial
