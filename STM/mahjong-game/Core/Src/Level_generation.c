#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#define TOTAL_PIECES 50

// Tile Groups
#define GRP_BAMBOO    0x00
#define GRP_CHARS     0x01
#define GRP_CIRCLES   0x02
#define GRP_WINDS     0x03
#define GRP_DRAGONS   0x04
#define GRP_FLOWERS   0x05
#define GRP_SEASONS   0x06

// Macro to pack Group + Value into 1 byte
#define PACK_TILE(grp, val) ((uint8_t)(((grp & 0x07) << 5) | (val & 0x1F)))

// The only state we actually need in RAM
uint8_t board_state[TOTAL_PIECES];

// Helper to push multiple copies of a tile range into the deck
void add_tiles(uint8_t *index, uint8_t group, int start_val, int count, int copies) {
    for (int v = 0; v < count; v++) {      // For each face value (e.g., 1, 2, 3...)
        for (int c = 0; c < copies; c++) { // Add 'N' copies of it
            board_state[(*index)++] = PACK_TILE(group, start_val + v);
        }
    }
}

void init_mahjong_game() {
    int idx = 0;

    // 1. Generate the Deck (Target: 50 pieces)
    // Add 4 copies of Bamboo 1-6 (24 tiles)
    add_tiles(&idx, GRP_BAMBOO, 1, 6, 4);

    // Add 4 copies of Circles 1-4 (16 tiles)
    add_tiles(&idx, GRP_CIRCLES, 1, 4, 4);

    // Add 2 copies of Dragon 1 (2 tiles)
    add_tiles(&idx, GRP_DRAGONS, 1, 1, 2);

    // Add 2 copies of Flowers 1-4 (8 tiles)
    add_tiles(&idx, GRP_FLOWERS, 1, 4, 2);

    // 2. Shuffle (Fisher-Yates)
    // The "Layout" is implicit. Pieces 0-24 are Layer 1, 25-40 Layer 2, etc.
    for (int i = TOTAL_PIECES - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t temp = board_state[i];
        board_state[i] = board_state[j];
        board_state[j] = temp;
    }

    printf("Game Initialized.\n");
}

int main() {
    srand(time(NULL));

    init_mahjong_game();

    // Verification: Print payload to send to PC
    printf("Payload (First 10 bytes): ");
    for(int i=0; i<10; i++) printf("0x%02X ", board_state[i]);
    printf("\n");

    return 0;
}
