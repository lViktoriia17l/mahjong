/*
 * command_list.c
 *
 *  Created on: 17 лют. 2026 р.
 *      Author: home
 */
/*
 *  #define CMD_START 0x01
	#define CMD_RESET 0x02
	#define CMD_SHUFFLE 0x03
	#define CMD_SELECT 0x04
	#define CMD_MATCH 0x05
 */
#include "mahjong.h"
#include <stdio.h>
#include <stdint.h>


void get_state()
{

}
void cmd_reset()
{

}

void cmd_shuffle()
{

}

// Internal state to remember the first clicked tile
// -1 indicates no tile is currently selected
static int8_t active_selection = -1;

// Helper to check if a tile exists (is not 0x00)
static int is_tile_valid(uint8_t index) {
    uint8_t* board = Mahjong_Get_Board_State(); // Access data from level_generation
    if (index >= TOTAL_PIECES) return 0;
    if (board[index] == 0x00) return 0;         // Tile already removed
    return 1;
}


uint8_t cmd_select(uint8_t index)
{
	if (!is_tile_valid(index)) {
	        return 0xFF; // Error: Tile doesn't exist
	}

	active_selection = index; // Store the selection
	return 0x00;
}

uint8_t cmd_match(uint8_t index)
{
	// 1. Validations
		if (active_selection == -1) {
			return 0xFF; // Error: No first tile selected
		}
		if (index == active_selection) {
			return 0xFF; // Error: Clicked the same tile twice
		}
		if (!is_tile_valid(index)) {
			return 0xFF;     // Error: Target tile invalid
		}

		// 2. Get the actual tile data
		uint8_t* board = Mahjong_Get_Board_State();
		uint8_t tile1 = board[active_selection];
		uint8_t tile2 = board[index];

		// 3. Decode Groups and Values
		uint8_t g1 = (tile1 >> 5) & 0x07;
		uint8_t v1 = tile1 & 0x1F;

		uint8_t g2 = (tile2 >> 5) & 0x07;
		uint8_t v2 = tile2 & 0x1F;

		// 4. Comparison Logic
		int is_match = 0;

		if (g1 == g2) {
		    // Special Rule: Flowers (5) and Seasons (6) match any other in the same group
		    if (g1 == GRP_FLOWERS || g1 == GRP_SEASONS) {
		        is_match = 1;
		    }
		    // Standard Rule: Values must match (e.g., Bamboo 2 == Bamboo 2)
		    else if (v1 == v2) {
		        is_match = 1;
		    }

		}
}

