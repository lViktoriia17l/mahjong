/*
 * mfhjong.h
 *
 *  Created on: 16 лют. 2026 р.
 *      Author: home
 */

#ifndef MAHJONG_H
#define MAHJONG_H

#include <stdint.h>

// Definitions
#define TOTAL_PIECES 50

#define CMD_START 0x01
#define CMD_RESET 0x02
#define CMD_SHUFFLE 0x03
#define CMD_SELECT 0x04
#define CMD_MATCH 0x05
#define CMD_GET_STATE 0x06

// Function Prototypes (Function summon)
void Mahjong_Init(void);                // Sets up the game engine
void Mahjong_Generate_New_Layout(void); // Generates/Shuffles the board
uint8_t* Mahjong_Get_Board_State(void); // Returns the pointer to the 50 bytes

#endif
