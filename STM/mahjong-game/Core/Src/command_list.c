/* command_list.c */
#include "mahjong.h"
#include <stdlib.h> // for rand()

// Internal state
static int8_t active_selection = -1;
static uint8_t shuffle_count = 0;
#define MAX_SHUFFLES 5

// --- Coordinate Helpers ---

// Returns 1 if a tile exists at this index, 0 otherwise
static int is_tile_present(uint8_t index) {
    uint8_t* board = Mahjong_Get_Board_State();
    if (index >= TOTAL_PIECES) return 0;
    return (board[index] != 0x00);
}

// Converts Layer/Row/Col to Index. Returns -1 if out of bounds.
static int get_index(int layer, int row, int col) {
    if (layer == 0) { // 5x5
        if (row < 0 || row >= 5 || col < 0 || col >= 5) return -1;
        return (row * 5) + col;
    }
    else if (layer == 1) { // 4x4
        if (row < 0 || row >= 4 || col < 0 || col >= 4) return -1;
        return 25 + (row * 4) + col;
    }
    else if (layer == 2) { // 3x3
        if (row < 0 || row >= 3 || col < 0 || col >= 3) return -1;
        return 41 + (row * 3) + col;
    }
    return -1;
}

// Converts Index to Layer/Row/Col
static void get_coord(uint8_t index, int* layer, int* row, int* col) {
    if (index < 25) {
        *layer = 0; *row = index / 5; *col = index % 5;
    } else if (index < 41) {
        *layer = 1; index -= 25; *row = index / 4; *col = index % 4;
    } else {
        *layer = 2; index -= 41; *row = index / 3; *col = index % 3;
    }
}

// --- The Core Rule: Is Tile Exposed? ---
static int is_tile_exposed(uint8_t index) {
    if (!is_tile_present(index)) return 0; // Tile doesn't exist

    int l, r, c;
    get_coord(index, &l, &r, &c);

    // 1. Check Z-Axis (Is it covered from above?)
    // A tile at Layer L(r,c) is covered by tiles in Layer L+1 at:
    // (r-1, c-1), (r-1, c), (r, c-1), (r, c)
    if (l < 2) {
        int next_l = l + 1;
        int blockers[] = {
            get_index(next_l, r - 1, c - 1), // Top-Left Overlay
            get_index(next_l, r - 1, c),     // Top-Right Overlay
            get_index(next_l, r, c - 1),     // Bottom-Left Overlay
            get_index(next_l, r, c)          // Bottom-Right Overlay
        };

        for (int i = 0; i < 4; i++) {
            if (blockers[i] != -1 && is_tile_present(blockers[i])) {
                return 0; // Blocked from above
            }
        }
    }

    // 2. Check X-Axis (Is it blocked on BOTH sides?)
    // Left Neighbor: (r, c-1)
    // Right Neighbor: (r, c+1)
    int idx_left = get_index(l, r, c - 1);
    int idx_right = get_index(l, r, c + 1);

    int left_blocked = (idx_left != -1 && is_tile_present(idx_left));
    int right_blocked = (idx_right != -1 && is_tile_present(idx_right));

    if (left_blocked && right_blocked) {
        return 0; // Blocked on both sides
    }

    return 1; // Exposed!
}

// --- Command Implementations ---

void cmd_reset(void) {
    active_selection = -1;
    shuffle_count = 0;
    Mahjong_Init();
    Mahjong_Generate_New_Layout();
}

void cmd_give_up(void) {
    cmd_reset();
}
uint8_t cmd_shuffle(void) {
    if (shuffle_count >= MAX_SHUFFLES) return 0xFF;

    uint8_t* board = Mahjong_Get_Board_State();
    uint8_t active_tiles[TOTAL_PIECES];
    uint8_t active_indices[TOTAL_PIECES];
    int count = 0;

    for (int i = 0; i < TOTAL_PIECES; i++) {
        if (board[i] != 0x00) {
            active_tiles[count] = board[i];
            active_indices[count] = i;
            count++;
        }
    }

    for (int i = count - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t temp = active_tiles[i];
        active_tiles[i] = active_tiles[j];
        active_tiles[j] = temp;
    }

    for (int i = 0; i < count; i++) {
        board[active_indices[i]] = active_tiles[i];
    }

    shuffle_count++;
    active_selection = -1;
    return 0x00;
}

uint8_t cmd_select(uint8_t index) {
    // UPDATED: Check if tile is exposed before allowing selection
    if (!is_tile_exposed(index)) return 0xFF;

    active_selection = index;
    return 0x00;
}

uint8_t cmd_match(uint8_t index) {
    if (active_selection == -1) return 0xFF;
    if (index == active_selection) return 0xFF;

    // UPDATED: Check if target tile is exposed
    if (!is_tile_exposed(index)) return 0xFF;

    uint8_t* board = Mahjong_Get_Board_State();
    uint8_t tile1 = board[active_selection];
    uint8_t tile2 = board[index];

    uint8_t g1 = (tile1 >> 5) & 0x07;
    uint8_t v1 = tile1 & 0x1F;
    uint8_t g2 = (tile2 >> 5) & 0x07;
    uint8_t v2 = tile2 & 0x1F;

    int is_match = 0;
    if (g1 == g2) {
        if (g1 == GRP_FLOWERS || g1 == GRP_SEASONS) is_match = 1;
        else if (v1 == v2) is_match = 1;
    }

    if (is_match) {
        board[active_selection] = 0x00;
        board[index] = 0x00;
        active_selection = -1;
        return 0x01;
    } else {
        active_selection = -1;
        return 0x00;
    }
}
