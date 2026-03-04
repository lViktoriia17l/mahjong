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
    if (current_layout == 0) { // Default 5x5 Square
        if (layer == 0) { if (row < 0 || row >= 5 || col < 0 || col >= 5) return -1; return (row * 5) + col; }
        if (layer == 1) { if (row < 0 || row >= 4 || col < 0 || col >= 4) return -1; return 25 + (row * 4) + col; }
        if (layer == 2) { if (row < 0 || row >= 3 || col < 0 || col >= 3) return -1; return 41 + (row * 3) + col; }
    } else { // Symmetrical Triangle Pyramid
        if (layer == 0) {
            if (row < 0 || row >= 7 || col < 0 || col > row) return -1;
            int base = 0; for(int i=0; i<row; i++) base += (i+1); return base + col;
        } else if (layer == 1) {
            if (row < 0 || row >= 5 || col < 0 || col > row) return -1;
            int base = 28; for(int i=0; i<row; i++) base += (i+1); return base + col;
        } else if (layer == 2) {
            if (row < 0 || row >= 3 || col < 0 || col > row) return -1;
            int base = 43; for(int i=0; i<row; i++) base += (i+1); return base + col;
        } else if (layer == 3) {
            if (row == 0 && col == 0) return 49;
        }
    }
    return -1;
}

// Converts Index to Layer/Row/Col
static void get_coord(uint8_t index, int* layer, int* row, int* col) {
    if (current_layout == 0) { // Default Square
        if (index < 25) { *layer = 0; *row = index / 5; *col = index % 5; }
        else if (index < 41) { *layer = 1; index -= 25; *row = index / 4; *col = index % 4; }
        else { *layer = 2; index -= 41; *row = index / 3; *col = index % 3; }
    } else { // Symmetrical Triangle Pyramid
        if (index < 28) {
            *layer = 0; int r = 0, sum = 0;
            while (sum + (r + 1) <= index) { sum += (r + 1); r++; }
            *row = r; *col = index - sum;
        } else if (index < 43) {
            *layer = 1; index -= 28; int r = 0, sum = 0;
            while (sum + (r + 1) <= index) { sum += (r + 1); r++; }
            *row = r; *col = index - sum;
        } else if (index < 49) {
            *layer = 2; index -= 43; int r = 0, sum = 0;
            while (sum + (r + 1) <= index) { sum += (r + 1); r++; }
            *row = r; *col = index - sum;
        } else {
            *layer = 3; *row = 0; *col = 0;
        }
    }
}

// --- The Core Rule: Is Tile Exposed? ---
static int is_tile_exposed(uint8_t index) {
    if (!is_tile_present(index)) return 0;

    int l, r, c;
    get_coord(index, &l, &r, &c);

    if (current_layout == 0) {
        // Square Coverage Logic
        int next_l = l + 1;
        int blockers[] = {
            get_index(next_l, r - 1, c - 1), get_index(next_l, r - 1, c),
            get_index(next_l, r, c - 1),     get_index(next_l, r, c)
        };
        for (int i = 0; i < 4; i++) {
            if (blockers[i] != -1 && is_tile_present(blockers[i])) return 0;
        }
    } else {
        // Symmetrical Triangle Coverage Logic
        int next_l = l + 1;
        // In this geometry, a tile from Layer L+1 Row R-1 perfectly overlaps
        // the left and right halves of the tiles directly below it.
        int blockers[] = {
            get_index(next_l, r - 1, c - 1), // Top-Left Overlay
            get_index(next_l, r - 1, c)      // Top-Right Overlay
        };
        for (int i = 0; i < 2; i++) {
            if (blockers[i] != -1 && is_tile_present(blockers[i])) return 0; // Blocked from above
        }
    }

    // X-Axis (Is it blocked on BOTH left and right sides?)
    // This logic applies to BOTH layout types perfectly!
    int idx_left = get_index(l, r, c - 1);
    int idx_right = get_index(l, r, c + 1);

    int left_blocked = (idx_left != -1 && is_tile_present(idx_left));
    int right_blocked = (idx_right != -1 && is_tile_present(idx_right));

    if (left_blocked && right_blocked) return 0; // Blocked on both sides

    return 1; // Exposed!
}


// --- Command Implementations ---

void cmd_reset(void) {
    active_selection = -1;
    shuffle_count = 0;
    Mahjong_Init();
    Mahjong_Generate_New_Layout(current_layout);
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

            // New win check logic
            uint8_t game_won = 1;
            for(int i = 0; i < TOTAL_PIECES; i++) {
                if(board[i] != 0x00) {
                    game_won = 0; // Found a tile, game is not over
                    break;
                }
            }

            if (game_won) {
                // Stop the timer and save the score!
                uint32_t final_time = Timer_GetSeconds();
                char* player_name = Mahjong_GetPlayerName();
                Add_HighScore(player_name, final_time);
            }

            return 0x01;
        } else {
            active_selection = -1;
            return 0x00;
        }
}

uint8_t cmd_hint(uint8_t *idx1, uint8_t *idx2) {
    uint8_t* board = Mahjong_Get_Board_State();

    for (int i = 0; i < TOTAL_PIECES; i++) {
        if (board[i] == 0 || !is_tile_exposed(i)) continue;

        for (int j = i + 1; j < TOTAL_PIECES; j++) {
            if (board[j] == 0 || !is_tile_exposed(j)) continue;

            uint8_t tile1 = board[i];
            uint8_t tile2 = board[j];

            // & 0x07 - це математична маска для читання бітів, не звертай уваги
            uint8_t grp1 = (tile1 >> 5) & 0x07;
            uint8_t grp2 = (tile2 >> 5) & 0x07;

            // Якщо це Квіти (5) або Сезони (6) - перевіряємо тільки групу
            if (grp1 == grp2 && (grp1 == 5 || grp1 == 6)) {
                *idx1 = (uint8_t)i;
                *idx2 = (uint8_t)j;
                return 1;
            }
            // Для всіх інших - перевіряємо повний збіг плитки
            else if (tile1 == tile2) {
                *idx1 = (uint8_t)i;
                *idx2 = (uint8_t)j;
                return 1;
            }
        }
    }
    return 0; // Пар не знайдено
}
