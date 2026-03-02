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
#define CMD_GIVE_UP   0x07
#define CMD_HINT      0x08
#define CMD_SET_NAME  0x09
#define CMD_GET_NAME  0x0A
#define CMD_GET_TIME  0x0B
// Tile Groups
#define GRP_FLOWERS   0b101
#define GRP_SEASONS   0b110

// High Scores
#define MAX_SCORES 10

// 16 bytes for name + 4 bytes for time = 20 bytes total (perfectly divisible by 4)
typedef struct {
    char name[16];
    uint32_t time;
} HighScore;

// Function Prototypes for Save/Load Highscore table
void Load_HighScores(void);
void Save_HighScores(void);
void Add_HighScore(const char* new_name, uint32_t new_time);

// --- Level Generation (Data) ---
void Mahjong_Init(void);
void Mahjong_Generate_New_Layout(void);
uint8_t* Mahjong_Get_Board_State(void);

// --- Command Logic (Game Controller) ---
void cmd_reset(void);
uint8_t cmd_shuffle(void);
uint8_t cmd_select(uint8_t index);
uint8_t cmd_match(uint8_t index);
uint8_t cmd_hint(uint8_t *idx1, uint8_t *idx2);
void cmd_give_up(void);

// Game State Functions
void Mahjong_SetPlayerName(const char* name);
char* Mahjong_GetPlayerName(void);
void Mahjong_Start_Timer(void);
uint32_t Mahjong_Get_Elapsed_Seconds(void);
void Timer_Start(void);
uint32_t Timer_GetSeconds(void);
void Timer_Tick(void);
#endif
