#include "main.h"
#include "mahjong.h"
#include <string.h>

#define FLASH_STORAGE_ADDRESS 0x0800FC00

// Declare the working RAM array
HighScore leaderboard[MAX_SCORES];

void Load_HighScores(void) {
    HighScore* flash_ptr = (HighScore*)FLASH_STORAGE_ADDRESS;

    if (flash_ptr[0].time == 0xFFFFFFFF) {
        // Flash is empty, fill with defaults
        for (int i = 0; i < MAX_SCORES; i++) {
            strcpy(leaderboard[i].name, "---");
            leaderboard[i].time = 999999;
        }
    } else {
        // Load from Flash
        memcpy(leaderboard, flash_ptr, sizeof(HighScore) * MAX_SCORES);
    }
}

void Save_HighScores(void) {
    HAL_FLASH_Unlock();

    FLASH_EraseInitTypeDef EraseInitStruct;
    uint32_t PageError = 0;
    EraseInitStruct.TypeErase   = FLASH_TYPEERASE_PAGES;
    EraseInitStruct.PageAddress = FLASH_STORAGE_ADDRESS;
    EraseInitStruct.NbPages     = 1;

    if (HAL_FLASHEx_Erase(&EraseInitStruct, &PageError) != HAL_OK) {
        HAL_FLASH_Lock();
        return;
    }

    uint32_t* ram_ptr = (uint32_t*)leaderboard;
    uint32_t address = FLASH_STORAGE_ADDRESS;
    uint32_t total_words = (sizeof(HighScore) * MAX_SCORES) / 4;

    for (uint32_t i = 0; i < total_words; i++) {
        HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, address, ram_ptr[i]);
        address += 4;
    }

    HAL_FLASH_Lock();
}

void Add_HighScore(const char* new_name, uint32_t new_time) {
    int insert_index = -1;

    for (int i = 0; i < MAX_SCORES; i++) {
        if (new_time < leaderboard[i].time) {
            insert_index = i;
            break;
        }
    }

    if (insert_index != -1) {
        for (int i = MAX_SCORES - 1; i > insert_index; i--) {
            leaderboard[i] = leaderboard[i - 1];
        }

        strncpy(leaderboard[insert_index].name, new_name, 15);
        leaderboard[insert_index].name[15] = '\0';
        leaderboard[insert_index].time = new_time;

        Save_HighScores();
    }
}
