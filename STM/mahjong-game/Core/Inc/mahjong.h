#ifndef MAHJONG_H
#define MAHJONG_H

#include <stdint.h>

#define TOTAL_PIECES   50
#define MAX_SCORES     10
#define MAX_SHUFFLES   5

// Команди
#define CMD_START       0x01
#define CMD_RESET       0x02
#define CMD_SHUFFLE     0x03
#define CMD_SELECT      0x04
#define CMD_MATCH       0x05
#define CMD_GIVE_UP     0x07
#define CMD_HINT        0x08
#define CMD_SET_NAME    0x09
#define CMD_GET_TIME    0x0B
#define CMD_GET_LEADERS 0x0C

typedef struct {
    char name[16];
    uint32_t time;
} HighScore;

// Глобальні змінні
extern HighScore leaderboard[MAX_SCORES];
extern uint8_t current_layout;

// Функції ядра та логіки
void Mahjong_Init(void);
void Mahjong_Generate_New_Layout(uint8_t layout_type);
uint8_t* Mahjong_Get_Board_State(void);
void Mahjong_SetPlayerName(const char* name);
char* Mahjong_GetPlayerName(void);

// Команди гри
void cmd_reset(void);
void cmd_give_up(void);
uint8_t cmd_shuffle(void);
uint8_t cmd_select(uint8_t index);
uint8_t cmd_match(uint8_t index);
uint8_t cmd_hint(uint8_t *idx1, uint8_t *idx2);

// Таймер та Збереження
void Timer_Start(void);
uint32_t Timer_GetSeconds(void);
void Timer_Tick(void);
void Load_HighScores(void);
void Save_HighScores(void);
void Add_HighScore(const char* new_name, uint32_t new_time);

#endif
