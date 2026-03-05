#include "mahjong.h"
#include <stdlib.h>
#include <string.h>

// Макрос для пакування плитки в 1 байт:
// Перші 3 біти — група (0-7), останні 5 біт — значення (0-31)
#define PACK_TILE(grp, val) ((uint8_t)(((grp & 0x07) << 5) | (val & 0x1F)))

/* --- Глобальні змінні стану --- */
static uint8_t board_state[TOTAL_PIECES];    // Масив, що зберігає всі плитки на полі
static char current_player_name[16] = "Player1";
uint8_t current_layout = 0;                  // Поточний тип розкладки (піраміда/трикутник)
volatile uint32_t hardware_seconds = 0;      // Лічильник секунд (змінюється в перериванні)
static uint8_t hw_timer_running = 0;         // Статус таймера (активний/зупинений)

/* --- Допоміжна функція додавання плиток --- */
// idx - вказівник на поточну позицію в масиві board_state
// grp - категорія плиток, start - початкове значення, count - кількість типів, copies - скільки копій кожної
static void add_tiles(uint8_t *idx, uint8_t grp, int start, int count, int copies) {
    for (int v = 0; v < count; v++)
        for (int c = 0; c < copies; c++)
            board_state[(*idx)++] = PACK_TILE(grp, start + v);
}

// Очищення ігрового поля
void Mahjong_Init(void) {
    memset(board_state, 0, TOTAL_PIECES);
}

// Генерація нового набору плиток та їх перемішування
void Mahjong_Generate_New_Layout(uint8_t layout_type) {
    current_layout = layout_type;
    uint8_t idx = 0;

    // Наповнення колоди згідно з правилами маджонгу (спрощено):
    add_tiles(&idx, 0, 1, 6, 4); // Бамбук: 6 видів по 4 копії
    add_tiles(&idx, 2, 1, 4, 4); // Кола: 4 види по 4 копії
    add_tiles(&idx, 4, 1, 1, 2); // Дракони: 1 вид, 2 копії
    add_tiles(&idx, 5, 1, 4, 2); // Квіти/Сезони: 4 види по 2 копії

    // Перемішування плиток (Shuffle), щоб вони стояли на випадкових місцях
    for (int i = TOTAL_PIECES - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t tmp = board_state[i];
        board_state[i] = board_state[j];
        board_state[j] = tmp;
    }
}

/* --- Геттери та Сеттери --- */

// Повертає вказівник на масив поля для передачі по UART або аналізу
uint8_t* Mahjong_Get_Board_State(void) {
    return board_state;
}

// Копіювання імені гравця (з захистом від переповнення рядка)
void Mahjong_SetPlayerName(const char* name) {
    strncpy(current_player_name, name, 15);
    current_player_name[15] = '\0';
}

char* Mahjong_GetPlayerName(void) {
    return current_player_name;
}

/* --- Робота з часом --- */

void Timer_Start(void) {
    hardware_seconds = 0;
    hw_timer_running = 1;
}

uint32_t Timer_GetSeconds(void) {
    return hardware_seconds;
}

// Ця функція має викликатися раз на секунду з переривання апаратного таймера (наприклад, TIM2)
void Timer_Tick(void) {
    if (hw_timer_running) hardware_seconds++;
}
