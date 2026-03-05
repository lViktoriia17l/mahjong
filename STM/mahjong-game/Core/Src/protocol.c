#include "protocol.h"
#include "mahjong.h"
#include <string.h>
#include <stdio.h>

extern UART_HandleTypeDef huart1;

static uint8_t rxBuffer[10];
static uint8_t rxPtr = 0;
static volatile uint8_t cmdStartDetected = 0;

// Таблиця для швидкого перетворення в Hex
static const char hexTable[] = "0123456789ABCDEF";

// XOR CRC розрахунок
static uint8_t calcLogicCRC(uint8_t cmd, uint8_t *data, uint8_t len) {
    uint8_t crc = cmd;
    for (int i = 0; i < len; i++) crc ^= data[i];
    return crc;
}

void Protocol_Init(void) {
    rxPtr = 0;
    cmdStartDetected = 0;
}

void Protocol_ReceiveByte(uint8_t byte) {
    // Ігноруємо пробільні символи
    if (byte == '\r' || byte == '\n' || byte == ' ') return;

    rxBuffer[rxPtr++] = byte;

    // Очікуємо послідовність "01FFFE"
    if (rxPtr == 6) {
        if (memcmp(rxBuffer, "01FFFE", 6) == 0) {
            cmdStartDetected = 1;
        }
        rxPtr = 0;
    }
}

void Protocol_Process(void) {
    if (!cmdStartDetected) return;

    uint8_t txBuf[110];
    int p = 0;

    // 1. Команда START (ASCII "01")
    txBuf[p++] = '0';
    txBuf[p++] = '1';

    // 2. Використовуємо реальну логіку гри для генерації
    Mahjong_Generate_New_Layout(current_layout);
    uint8_t *field = Mahjong_Get_Board_State();

    // 3. Конвертація поля в ASCII Hex (50 байт -> 100 символів)
    for (int i = 0; i < TOTAL_PIECES; i++) {
        txBuf[p++] = hexTable[(field[i] >> 4) & 0x0F];
        txBuf[p++] = hexTable[field[i] & 0x0F];
    }

    // 4. Розрахунок CRC (по логічним байтам, не по ASCII)
    uint8_t crc = calcLogicCRC(CMD_START, field, TOTAL_PIECES);
    txBuf[p++] = hexTable[(crc >> 4) & 0x0F];
    txBuf[p++] = hexTable[crc & 0x0F];

    // 5. Завершення
    txBuf[p++] = '\r';
    txBuf[p++] = '\n';

    HAL_UART_Transmit(&huart1, txBuf, p, 500);
    cmdStartDetected = 0;
}
