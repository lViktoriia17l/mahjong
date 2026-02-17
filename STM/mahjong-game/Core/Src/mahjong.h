/* mahjong.h */
#ifndef MAHJONG_H
#define MAHJONG_H

#include <stdint.h>

// Definitions
#define TOTAL_PIECES 50

// Commands
#define CMD_START     0x01
#define CMD_RESET     0x02
#define CMD_SHUFFLE   0x03
#define CMD_SELECT    0x04
#define CMD_MATCH     0x05
#define CMD_GET_STATE 0x06

// Tile Groups
#define GRP_FLOWERS   0b101
#define GRP_SEASONS   0b110

// --- Level Generation (Data) ---
void Mahjong_Init(void);
void Mahjong_Generate_New_Layout(void);
uint8_t* Mahjong_Get_Board_State(void);

// --- Command Logic (Game Controller) ---
void cmd_reset(void);
uint8_t cmd_shuffle(void);
uint8_t cmd_select(uint8_t index);
uint8_t cmd_match(uint8_t index);

#endif
