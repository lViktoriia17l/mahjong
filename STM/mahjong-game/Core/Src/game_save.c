#include "mahjong.h"
#include "main.h"
#include <string.h>

// Адреса у Flash-пам'яті, де будуть зберігатися рекорди.
#define FLASH_STORAGE_ADDRESS 0x0800FC00
HighScore leaderboard[MAX_SCORES];

/* --- Завантаження рекордів при старті --- */
void Load_HighScores(void) {
    HighScore* flash_ptr = (HighScore*)FLASH_STORAGE_ADDRESS;

    // Якщо перший байт пам'яті 0xFF, це означає, що Flash чиста (за замовчуванням)
    if (flash_ptr[0].time == 0xFFFFFFFF) {
        // Ініціалізуємо таблицю порожніми значеннями
        for (int i = 0; i < MAX_SCORES; i++) {
            strcpy(leaderboard[i].name, "---");
            leaderboard[i].time = 999999;
        }
    } else {
        // Якщо дані є — копіюємо їх з Flash в оперативну пам'ять (масив)
        memcpy(leaderboard, flash_ptr, sizeof(leaderboard));
    }
}

/* --- Запис рекордів у Flash --- */
void Save_HighScores(void) {
    HAL_FLASH_Unlock(); // Розблокування можливості запису у Flash

    // Налаштування для очищення сторінки (Flash не можна записати без очищення)
    FLASH_EraseInitTypeDef erase = {FLASH_TYPEERASE_PAGES, FLASH_STORAGE_ADDRESS, 1};
    uint32_t err = 0;

    // Стираємо сторінку перед записом нових даних
    if (HAL_FLASHEx_Erase(&erase, &err) == HAL_OK) {
        uint32_t* data = (uint32_t*)leaderboard;
        // Записуємо дані по 4 байти (WORD)
        for (uint32_t i = 0; i < (sizeof(leaderboard)/4); i++) {
            HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, FLASH_STORAGE_ADDRESS + (i*4), data[i]);
        }
    }
    HAL_FLASH_Lock(); // Заблокування Flash для безпеки
}

/* --- Додавання нового результату --- */
void Add_HighScore(const char* new_name, uint32_t new_time) {
    int idx = -1;

    // 1. Перевірка: чи цей гравець вже є у списку?
    for (int i = 0; i < MAX_SCORES; i++) {
        if (strcmp(leaderboard[i].name, new_name) == 0) {
            // Якщо його новий час гірший за старий — нічого не робимо
            if (new_time >= leaderboard[i].time) return;

            // Якщо результат кращий — видаляємо старий запис, щоб вставити новий на правильне місце
            for (int j = i; j < MAX_SCORES - 1; j++) leaderboard[j] = leaderboard[j+1];
            leaderboard[MAX_SCORES-1].time = 999999;
            break;
        }
    }

    // 2. Пошук позиції (індексу) для нового рекорду (сортування від меншого часу до більшого)
    for (int i = 0; i < MAX_SCORES; i++) {
        if (new_time < leaderboard[i].time) { idx = i; break; }
    }

    // 3. Якщо результат достатньо хороший для топ-списку
    if (idx != -1) {
        // Зсуваємо всі результати нижче на одну позицію
        for (int i = MAX_SCORES - 1; i > idx; i--) leaderboard[i] = leaderboard[i-1];

        // Вставляємо нові дані
        strncpy(leaderboard[idx].name, new_name, 15);
        leaderboard[idx].name[15] = '\0';
        leaderboard[idx].time = new_time;

        // Обов'язково зберігаємо оновлений список у Flash
        Save_HighScores();
    }
}
