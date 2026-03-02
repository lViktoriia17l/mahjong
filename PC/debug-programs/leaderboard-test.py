import serial
import struct
import time

# Налаштування (зміни COM-порт на свій)
SERIAL_PORT = "COM5" 
BAUD_RATE = 115200
CMD_GET_LEADERS = 0x0C

def calculate_xor_crc(data):
    """Розрахунок CRC за логікою: CMD ^ DATA[0] ^ DATA[1] ^ ..."""
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

def test_read_leaderboard():
    try:
        # Відкриваємо порт
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2.0)
        print(f"--- Підключено до {SERIAL_PORT} ---")

        # 1. Формуємо пакет запиту [CMD, DATA, CRC]
        # Для запиту дані зазвичай 0x00
        request_packet = bytearray([CMD_GET_LEADERS, 0x00])
        request_packet.append(calculate_xor_crc(request_packet))
        
        print(f"Відправка запиту: {request_packet.hex().upper()}")
        ser.write(request_packet)

        # 2. Очікуємо відповідь: 1 (CMD) + 200 (10 лідерів * 20б) + 1 (CRC) = 202 байти
        expected_len = 202
        print(f"Очікування {expected_len} байт від STM32...")
        
        raw_response = ser.read(expected_len)

        if len(raw_response) < expected_len:
            print(f"Помилка: Отримано лише {len(raw_response)} байт. Перевір код STM32.")
            return

        # 3. Перевірка CRC
        received_data_for_crc = raw_response[:-1]
        received_crc = raw_response[-1]
        calculated_crc = calculate_xor_crc(received_data_for_crc)

        if received_crc != calculated_crc:
            print(f"Помилка CRC! Отримано: {hex(received_crc)}, Очікувалось: {hex(calculated_crc)}")
            # Продовжимо для тесту, щоб побачити, що прийшло
        else:
            print("CRC підтверджено!")

        # 4. Парсинг даних
        # Структура: 16 байт (рядок) + 4 байти (uint32)
        payload = raw_response[1:-1] # Відрізаємо CMD та CRC
        
        print("\n=== ТАБЛИЦЯ ЛІДЕРІВ (STM32) ===")
        print(f"{'№':<3} | {'Імя':<16} | {'Час (сек)':<10}")
        print("-" * 35)

        for i in range(10):
            chunk = payload[i*20 : (i+1)*20]
            # <16sI: Little-endian, рядок 16 байт, unsigned int 4 байти
            name_raw, play_time = struct.unpack('<16sI', chunk)
            
            # Декодуємо ім'я, видаляючи нульові байти \x00
            name = name_raw.decode('utf-8').strip('\x00')
            
            # Виводимо результат
            display_time = play_time if play_time < 999999 else "---"
            print(f"{i+1:<3} | {name:<16} | {display_time:<10}")

    except Exception as e:
        print(f"Помилка: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("\nПорт закритий.")

if __name__ == "__main__":
    test_read_leaderboard()