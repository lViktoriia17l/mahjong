/* mahjong.c */
#include "mahjong.h"
#include <stdlib.h>
#include <string.h>

// --- Private Macros ---
#define GRP_BAMBOO    0b000
#define GRP_CHARS     0b001
#define GRP_CIRCLES   0b010
#define GRP_WINDS     0b011
#define GRP_DRAGONS   0b100
#define GRP_FLOWERS   0b101
#define GRP_SEASONS   0b110

#define PACK_TILE(grp, val) ((uint8_t)(((grp & 0x07) << 5) | (val & 0x1F)))

// --- Private Variables ---
static uint8_t board_state[TOTAL_PIECES];

// --- Private Helper Functions ---
static void add_tiles(uint8_t *index, uint8_t group, int start_val, int count, int copies) {
    for (int v = 0; v < count; v++) {
        for (int c = 0; c < copies; c++) {
            board_state[(*index)++] = PACK_TILE(group, start_val + v);
        }
    }
}

// --- Public Function Implementations ---

void Mahjong_Init(void) {
    // Any one-time setup (like clearing memory) goes here
    memset(board_state, 0, TOTAL_PIECES);
}

void Mahjong_Generate_New_Layout(void) {
    int idx = 0;

    // 1. Fill Deck
    add_tiles(&idx, GRP_BAMBOO, 1, 6, 4);
    add_tiles(&idx, GRP_CIRCLES, 1, 4, 4);
    add_tiles(&idx, GRP_DRAGONS, 1, 1, 2);
    add_tiles(&idx, GRP_FLOWERS, 1, 4, 2);

    // 2. Shuffle (Fisher-Yates)
    for (int i = TOTAL_PIECES - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t temp = board_state[i];
        board_state[i] = board_state[j];
        board_state[j] = temp;
    }
}

uint8_t* Mahjong_Get_Board_State(void) {
    return board_state;
}
