/* --- Mahjong-Game on STM32 final build --- */
/* ------- Last checked by @isWeezzy ------- */
/* --------------- Includes ---------------- */
#include "main.h"
#include "mahjong.h"
#include <stdlib.h>
#include <string.h>

/* --------- Периферійні дескриптори -------- */
TIM_HandleTypeDef htim2;    		// Таймер для відстеження ігрового часу
UART_HandleTypeDef huart1;  		// UART для зв'язку з верхнім рівнем (ПК/додаток)

/* ------------ Буфери протоколу ------------ */
uint8_t rx_packet[3];               // Вхідний пакет: [Команда, Дані, CRC] (завжди 3 байти)
uint8_t tx_packet[210];             // Вихідний пакет: [Команда, Дані (до 200 байт), CRC]
volatile uint8_t packet_ready = 0;  // Прапорець переривання: 1, якщо отримано новий пакет

/* ------- Прототипи системних функцій ------ */
void SystemClock_Config(void);
static void MX_USART1_UART_Init(void);
static void MX_TIM2_Init(void);

/* ---- Обчислення контрольної суми (CRC) --- */
uint8_t Calc_CRC(uint8_t *data, uint8_t len) {
    uint8_t crc = 0;
    for(int i = 0; i < len; i++) crc ^= data[i];
    return crc;
}

/* ------- Обробники переривань UART -------- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) packet_ready = 1;
}

// Обробка помилок UART (наприклад, переповнення буфера)
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        __HAL_UART_CLEAR_OREFLAG(huart); // Очищення прапорця Overrun
        packet_ready = 0;
        // Перезапуск читання після помилки
        HAL_UART_Receive_IT(&huart1, rx_packet, 3);
    }
}

int main(void) {
    /* Ініціалізація заліза та бібліотек */
    HAL_Init();
    SystemClock_Config();
    MX_USART1_UART_Init();
    MX_TIM2_Init();

    Mahjong_Init();       // Ініціалізація ігрової логіки
    Load_HighScores();    // Завантаження таблиці лідерів з пам'яті

    /* Запуск таймера та очікування першої команди через переривання */
    HAL_TIM_Base_Start_IT(&htim2);
    HAL_UART_Receive_IT(&huart1, rx_packet, 3);

    while (1) {
        // Якщо прапорець піднятий у перериванні — обробляємо пакет
        if (packet_ready) {
            uint8_t cmd = rx_packet[0];   // Код команди
            uint8_t data = rx_packet[1];  // Параметр команди

            // Перевірка контрольної суми вхідного пакету
            if (Calc_CRC(rx_packet, 2) == rx_packet[2]) {
                memset(tx_packet, 0, sizeof(tx_packet));
                tx_packet[0] = cmd;       // Відповідь зазвичай починається з коду тієї ж команди
                uint16_t tx_len = 3;      // Стандартна довжина відповіді (CMD, DATA, CRC)

                switch (cmd) {
                    case CMD_START:
                        Mahjong_Generate_New_Layout(data); // Створення поля
                        Timer_Start();                     // Запуск відліку часу
                        // Копіюємо стан дошки (50 байт) у пакет відповіді
                        memcpy(&tx_packet[1], Mahjong_Get_Board_State(), 50);
                        tx_len = 52; // CMD + 50 байт дошки + CRC
                        break;

                    case CMD_RESET:
                        cmd_reset();
                        tx_packet[1] = 0x00; // Підтвердження скидання
                        break;

                    case CMD_SHUFFLE:
                        // Перемішування плиток, якщо можливо
                        if (cmd_shuffle() == 0xFF) tx_packet[1] = 0xFF; // Помилка
                        else {
                            memcpy(&tx_packet[1], Mahjong_Get_Board_State(), 50);
                            tx_len = 52;
                        }
                        break;

                    case CMD_SELECT:
                        tx_packet[1] = cmd_select(data); // Вибір плитки
                        break;

                    case CMD_MATCH:
                        tx_packet[1] = cmd_match(data);  // Спроба знайти пару
                        break;

                    case CMD_GIVE_UP:
                        cmd_give_up();
                        tx_packet[1] = 0x00;
                        break;

                    case CMD_HINT: {
                        uint8_t idx1, idx2;
                        if (cmd_hint(&idx1, &idx2)) { // Пошук доступної пари
                            tx_packet[1] = idx1;
                            tx_packet[2] = idx2;
                        } else tx_packet[1] = 100;    // Код "підказок немає"
                        tx_len = 4;
                        break;
                    }

                    case CMD_SET_NAME:
                        if (data > 0 && data <= 10) { // data тут — довжина імені
                            uint8_t name_buf[12];
                            __HAL_UART_CLEAR_OREFLAG(&huart1);
                            // Додаткове синхронне читання самого імені після команди
                            if (HAL_UART_Receive(&huart1, name_buf, data + 1, 500) == HAL_OK) {
                                if (Calc_CRC(name_buf, data) == name_buf[data]) {
                                    char name[11] = {0};
                                    memcpy(name, name_buf, data);
                                    Mahjong_SetPlayerName(name);
                                }
                            }
                        }
                        tx_packet[1] = 0x00;
                        break;

                    case CMD_GET_TIME: {
                        uint32_t elapsed = Timer_GetSeconds();
                        // Розбиття 32-бітного числа на 4 байти для передачі
                        tx_packet[1] = (elapsed >> 24) & 0xFF;
                        tx_packet[2] = (elapsed >> 16) & 0xFF;
                        tx_packet[3] = (elapsed >> 8) & 0xFF;
                        tx_packet[4] = elapsed & 0xFF;
                        tx_len = 52; // Використовується фіксований розмір для стабільності
                        break;
                    }

                    case CMD_GET_LEADERS:
                        // Копіювання всієї таблиці лідерів (200 байт)
                        memcpy(&tx_packet[1], leaderboard, 200);
                        tx_packet[201] = Calc_CRC(tx_packet, 201);
                        HAL_UART_Transmit(&huart1, tx_packet, 202, 1000);
                        goto reset_rx; // Пропускаємо стандартну відправку в кінці switch
                }

                // Фінальне обчислення CRC та відправка відповіді клієнту
                tx_packet[tx_len - 1] = Calc_CRC(tx_packet, tx_len - 1);
                HAL_UART_Transmit(&huart1, tx_packet, tx_len, 100);
            }

        reset_rx:
            // Скидання прапорця та підготовка до отримання наступної команди
            packet_ready = 0;
            HAL_UART_Receive_IT(&huart1, rx_packet, 3);
        }
    }
}

/* --- !!!
 * 	EN:	Part of the STM32 configuration, review/changing it at your own risk
 * 	UA:	Частина по конфігурації STM32, перегляд її/зміни його робите тільки на свій страх та ризик
 * 		(я вас знайду, якщо ви щось зламаєте)
 *  --- */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL12;
  RCC_OscInitStruct.PLL.PREDIV = RCC_PREDIV_DIV1;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }


  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }

  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART1;
  PeriphClkInit.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK1;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

static void MX_TIM2_Init(void)
{
  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 47999;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 999;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  HAL_NVIC_SetPriority(TIM2_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(TIM2_IRQn);
}

static void MX_USART1_UART_Init(void)
{
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
}

void Error_Handler(void) {
    __disable_irq();
    while (1);
}
