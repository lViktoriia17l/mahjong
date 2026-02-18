/* command_list.c */
#include "mahjong.h"
#include <stdlib.h> // for rand()

// Internal state to remember the first clicked tile
static int8_t active_selection = -1;
static uint8_t shuffle_count = 0;
#define MAX_SHUFFLES 5

// --- Helper Functions ---
static int is_tile_valid(uint8_t index) {
    uint8_t* board = Mahjong_Get_Board_State();
    if (index >= TOTAL_PIECES) return 0;
    if (board[index] == 0x00) return 0; // Tile already removed
    return 1;
}

// --- Command Implementations ---

void cmd_reset(void) {
    active_selection = -1;
    shuffle_count = 0;
    Mahjong_Init();
    Mahjong_Generate_New_Layout();
}

uint8_t cmd_shuffle(void) {
    if (shuffle_count >= MAX_SHUFFLES) return 0xFF; // Error: Limit reached

    uint8_t* board = Mahjong_Get_Board_State();
    uint8_t active_tiles[TOTAL_PIECES];
    uint8_t active_indices[TOTAL_PIECES];
    int count = 0;

    // 1. Collect valid tiles
    for (int i = 0; i < TOTAL_PIECES; i++) {
        if (board[i] != 0x00) {
            active_tiles[count] = board[i];
            active_indices[count] = i;
            count++;
        }
    }

    // 2. Fisher-Yates Shuffle
    for (int i = count - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t temp = active_tiles[i];
        active_tiles[i] = active_tiles[j];
        active_tiles[j] = temp;
    }

    // 3. Place back
    for (int i = 0; i < count; i++) {
        board[active_indices[i]] = active_tiles[i];
    }

    shuffle_count++;
    active_selection = -1; // Deselect to prevent bugs
    return 0x00; // Success
}

uint8_t cmd_select(uint8_t index) {
    if (!is_tile_valid(index)) return 0xFF;
    active_selection = index;
    return 0x00;
}

uint8_t cmd_match(uint8_t index) {
    // 1. Validations
    if (active_selection == -1) return 0xFF; // No start tile
    if (index == active_selection) return 0xFF; // Same tile
    if (!is_tile_valid(index)) return 0xFF;

    // 2. Get Data
    uint8_t* board = Mahjong_Get_Board_State();
    uint8_t tile1 = board[active_selection];
    uint8_t tile2 = board[index];

    uint8_t g1 = (tile1 >> 5) & 0x07;
    uint8_t v1 = tile1 & 0x1F;
    uint8_t g2 = (tile2 >> 5) & 0x07;
    uint8_t v2 = tile2 & 0x1F;

    // 3. Logic
    int is_match = 0;
    if (g1 == g2) {
        if (g1 == GRP_FLOWERS || g1 == GRP_SEASONS) is_match = 1;
        else if (v1 == v2) is_match = 1;
    }

    // 4. Execution
    if (is_match) {
        board[active_selection] = 0x00; // Remove T1
        board[index] = 0x00;            // Remove T2
        active_selection = -1;
        return 0x01; // Success
    } else {
        active_selection = -1; // Deselect on mismatch
        return 0x00; // Fail
    }
}
