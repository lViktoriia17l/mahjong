#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "main.h"

// Функції протоколу
void Protocol_Init(void);
void Protocol_Process(void);
void Protocol_ReceiveByte(uint8_t byte);

#endif
