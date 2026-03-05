#include "mahjong.h"
#include <stdlib.h>

static int8_t active_selection = -1; // Індекс поточної вибраної плитки (-1, якщо нічого не вибрано)
static uint8_t shuffle_count = 0;    // Лічильник перемішувань (зазвичай обмежений правилами)

// --- Допоміжні функції координат ---

// Перевіряє, чи є плитка в цій комірці (чи не порожня вона)
static int is_tile_present(uint8_t index) {
    return (index < TOTAL_PIECES && Mahjong_Get_Board_State()[index] != 0);
}

// Перетворює 3D координати (L - шар, R - рядок, C - стовпець) в лінійний індекс масиву
static int get_index(int l, int r, int c) {
    if (current_layout == 0) { // Прямокутна піраміда
        if (l == 0 && r >= 0 && r < 5 && c >= 0 && c < 5) return (r * 5) + c;
        if (l == 1 && r >= 0 && r < 4 && c >= 0 && c < 4) return 25 + (r * 4) + c;
        if (l == 2 && r >= 0 && r < 3 && c >= 0 && c < 3) return 41 + (r * 3) + c;
    } else { // Трикутна або інша складна форма
        int base[] = {0, 28, 43, 49};
        int sizes[] = {7, 5, 3, 1};
        if (l < 4 && r >= 0 && r < sizes[l] && c >= 0 && c <= r) {
            int row_offset = 0;
            for(int i=0; i<r; i++) row_offset += (i+1); // Розрахунок зміщення для трикутної сітки
            return base[l] + row_offset + c;
        }
    }
    return -1; // Невірні координати
}

// Зворотна операція: отримує 3D координати з лінійного індексу
static void get_coord(uint8_t idx, int* l, int* r, int* c) {
    if (current_layout == 0) {
        if (idx < 25) { *l = 0; *r = idx / 5; *c = idx % 5; }
        else if (idx < 41) { *l = 1; idx -= 25; *r = idx / 4; *c = idx % 4; }
        else { *l = 2; idx -= 41; *r = idx / 3; *c = idx % 3; }
    } else {
        int limits[] = {28, 43, 49, 50}, base = 0;
        for(int i=0; i<4; i++) {
            if (idx < limits[i]) {
                *l = i; int r_idx = idx - base, row = 0, sum = 0;
                while (sum + (row + 1) <= r_idx) { sum += (row + 1); row++; }
                *r = row; *c = r_idx - sum; return;
            }
            base = limits[i];
        }
    }
}

// Перевірка, чи "відкрита" плитка (чи можна її брати)
// Згідно з правилами: зверху не повинно бути плиток, і хоча б один бік (лівий чи правий) має бути вільним
static int is_tile_exposed(uint8_t index) {
    if (!is_tile_present(index)) return 0;
    int l, r, c; get_coord(index, &l, &r, &c);

    // 1. Перевірка зверху (чи не заблокована плитка верхнім шаром)
    int next_l = l + 1;
    if (current_layout == 0) {
        // У прямокутному лейауті перевіряємо 4 сусідні точки зверху
        int b[] = {get_index(next_l, r-1, c-1), get_index(next_l, r-1, c), get_index(next_l, r, c-1), get_index(next_l, r, c)};
        for(int i=0; i<4; i++) if (b[i] != -1 && is_tile_present(b[i])) return 0;
    } else {
        // У трикутному — 2 точки
        int b[] = {get_index(next_l, r-1, c-1), get_index(next_l, r-1, c)};
        for(int i=0; i<2; i++) if (b[i] != -1 && is_tile_present(b[i])) return 0;
    }

    // 2. Перевірка боків (заблокована, якщо і зліва, і справа є сусіди)
    if (is_tile_present(get_index(l, r, c-1)) && is_tile_present(get_index(l, r, c+1))) return 0;

    return 1; // Плитка вільна для ходу
}

// Скидання гри до початкового стану
void cmd_reset(void) {
    active_selection = -1;
    shuffle_count = 0;
    Mahjong_Init();
    Mahjong_Generate_New_Layout(current_layout);
}

void cmd_give_up(void) { cmd_reset(); }

// Перемішування плиток, що залишилися на полі (якщо гра зайшла у глухий кут)
uint8_t cmd_shuffle(void) {
    if (shuffle_count >= MAX_SHUFFLES) return 0xFF; // Вичерпано ліміт перемішувань
    uint8_t* board = Mahjong_Get_Board_State();
    uint8_t tiles[TOTAL_PIECES], ids[TOTAL_PIECES];
    int count = 0;

    // Збираємо всі наявні плитки та їх позиції
    for (int i = 0; i < TOTAL_PIECES; i++) if (board[i]) { tiles[count] = board[i]; ids[count++] = i; }

    // Алгоритм Фішера-Єйтса для випадкового перемішування
    for (int i = count - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        uint8_t tmp = tiles[i]; tiles[i] = tiles[j]; tiles[j] = tmp;
    }

    // Повертаємо перемішані плитки назад на ті ж самі позиції
    for (int i = 0; i < count; i++) board[ids[i]] = tiles[i];

    shuffle_count++;
    active_selection = -1;
    return 0;
}

// Вибір плитки гравцем
uint8_t cmd_select(uint8_t index) {
    if (!is_tile_exposed(index)) return 0xFF; // Не можна вибрати заблоковану плитку
    active_selection = index;
    return 0;
}

// Спроба поєднати вибрану плитку з іншою
uint8_t cmd_match(uint8_t index) {
    // Перевірка валідності: чи вибрано щось раніше, чи це не та сама плитка, чи вона відкрита
    if (active_selection == -1 || index == active_selection || !is_tile_exposed(index)) return 0xFF;

    uint8_t* b = Mahjong_Get_Board_State();
    uint8_t t1 = b[active_selection], t2 = b[index];

    // Витягуємо групу плитки (верхні 3 біти)
    uint8_t g1 = (t1 >> 5) & 7, g2 = (t2 >> 5) & 7;

    // Умови збігу:
    // 1. Однакова група ТА (Група 5 або 6 (бонусні) АБО абсолютно однакові ID плиток)
    if (g1 == g2 && (g1 == 5 || g1 == 6 || t1 == t2)) {
        b[active_selection] = b[index] = 0; // Видаляємо пару з поля
        active_selection = -1;

        // Перевірка на перемогу (чи залишилися ще плитки)
        for(int i=0; i<TOTAL_PIECES; i++) if(b[i]) return 1;

        // Якщо порожньо — додаємо результат у таблицю лідерів
        Add_HighScore(Mahjong_GetPlayerName(), Timer_GetSeconds());
        return 1;
    }

    active_selection = -1; // Скидаємо вибір, якщо не співпало
    return 0;
}

// Пошук підказки (пари доступних плиток)
uint8_t cmd_hint(uint8_t *idx1, uint8_t *idx2) {
    uint8_t* b = Mahjong_Get_Board_State();
    // Подвійний цикл для пошуку пари серед усіх плиток
    for (int i = 0; i < TOTAL_PIECES; i++) {
        if (!b[i] || !is_tile_exposed(i)) continue;
        for (int j = i + 1; j < TOTAL_PIECES; j++) {
            if (!b[j] || !is_tile_exposed(j)) continue;

            uint8_t g1 = (b[i]>>5)&7, g2 = (b[j]>>5)&7;
            if (g1 == g2 && (g1 == 5 || g1 == 6 || b[i] == b[j])) {
                *idx1 = i; *idx2 = j; // Повертаємо індекси знайденої пари
                return 1;
            }
        }
    }
    return 0; // Підказок немає
}
