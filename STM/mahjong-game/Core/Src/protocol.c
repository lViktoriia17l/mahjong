#include "protocol.h"
#include <string.h>
#include <stdlib.h>

extern UART_HandleTypeDef huart1;

#define FIELD_SIZE 50
static uint8_t gameField[FIELD_SIZE];
static char rxBuffer[10];
static uint8_t rxPtr = 0;
static volatile uint8_t cmdStartDetected = 0;

const char hexTable[] = "0123456789ABCDEF";

// Функція розрахунку CRC (XOR всіх байтів)
static uint8_t calcLogicCRC(uint8_t cmd, uint8_t *data, uint8_t len) {
    uint8_t crc = cmd;
    for (int i = 0; i < len; i++) {
        crc ^= data[i];
    }
    return crc;
}

void Protocol_ReceiveByte(uint8_t byte) {
    if (byte == '\r' || byte == '\n' || byte == ' ') return;

    rxBuffer[rxPtr++] = byte;

    // Чекаємо команду "01FFFE" (6 символів)
    if (rxPtr == 6) {
        if (strncmp(rxBuffer, "01FFFE", 6) == 0) {
            cmdStartDetected = 1;
        }
        rxPtr = 0;
    }
}

void Protocol_Process(void) {
    if (cmdStartDetected) {
        uint8_t txBuf[110]; // 2 (CMD) + 100 (DATA) + 2 (CRC) + 2 (\r\n)
        int p = 0;

        // 1. Команда START (0x01)
        txBuf[p++] = '0';
        txBuf[p++] = '1';

        // 2. Генерація поля (50 байтів)
        for (int i = 0; i < FIELD_SIZE; i++) {
            // Тут твоя логіка тайлів: група (біти 7-5) та значення (біти 4-0)
            uint8_t group = (rand() % 7) << 5;
            uint8_t value = (rand() % 9) + 1;
            gameField[i] = group | value;

            // Перетворюємо байт у 2 ASCII символи
            txBuf[p++] = hexTable[(gameField[i] >> 4) & 0x0F];
            txBuf[p++] = hexTable[gameField[i] & 0x0F];
        }

        // 3. Розрахунок та додавання CRC
        uint8_t crc = calcLogicCRC(0x01, gameField, FIELD_SIZE);
        txBuf[p++] = hexTable[(crc >> 4) & 0x0F];
        txBuf[p++] = hexTable[crc & 0x0F];

        // 4. Завершення рядка
        txBuf[p++] = '\r';
        txBuf[p++] = '\n';

        HAL_UART_Transmit(&huart1, txBuf, p, 500);
        cmdStartDetected = 0;
    }
}
