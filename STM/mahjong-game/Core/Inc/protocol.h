#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "main.h"

// Коди команд
#define CMD_START     0x01
#define CMD_RESET     0x02
#define CMD_SHUFFLE   0x03
#define CMD_SELECT    0x04
#define CMD_MATCH     0x05
#define CMD_GET_STATE 0x06

void Protocol_Init(void);
void Protocol_Process(void);
void Protocol_ReceiveByte(uint8_t byte);

#endif
