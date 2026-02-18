/*---------------------------- mahjong-game build 2 --------------------------*/
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h> // For rand

/* USER CODE BEGIN Includes */
#include "mahjong.h" // <--- 1. Summon the module
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define CMD_START 0x01
#define CMD_RESET 0x02
#define CMD_SHUFFLE 0x03
#define CMD_SELECT 0x04
#define CMD_MATCH 0x05
#define CMD_GET_STATE 0x06
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart1;

/* USER CODE BEGIN PV */
/* --- Protocol Buffers --- */
uint8_t rx_packet[3];       // [CMD, DATA, CRC] - Fixed 3 bytes
uint8_t tx_packet[52];      // [CMD, 50xDATA, CRC]
volatile uint8_t packet_ready = 0; // Flag to tell Main that data arrived
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);
/* USER CODE BEGIN PFP */
uint8_t Calc_CRC(uint8_t *data, uint8_t len);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* --------- Helper: CRC Calculation --------- */
uint8_t Calc_CRC(uint8_t *data, uint8_t len) {
    uint8_t crc = 0;
    for(int i=0; i<len; i++) crc ^= data[i];
    return crc;
}

/* --------- UART RX callback (Interrupt) --------- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        // We received exactly 3 bytes into rx_packet
        packet_ready = 1;

        // Note: We do NOT restart the interrupt here immediately.
        // We restart it in the main loop after processing to prevent
        // overwriting the buffer while we are reading it.
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */
  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_USART1_UART_Init();

  /* USER CODE BEGIN 2 */
  // --- 2. Initialize Game Engine ---
  Mahjong_Init();

  // Seed Randomness (Uses system uptime)
  srand(HAL_GetTick());

  //HAL_UART_Transmit(&huart1, (uint8_t*)"UART READY (BINARY MODE)\r\n", 26, 100);

  // Start listening for the first 3-byte command
  HAL_UART_Receive_IT(&huart1, rx_packet, 3);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
    while (1)
    {
        if (packet_ready)
        {
            packet_ready = 0;

            uint8_t cmd = rx_packet[0];
            uint8_t data_byte = rx_packet[1];
            uint8_t received_crc = rx_packet[2];

            // Check CRC
            if ((cmd ^ data_byte) == received_crc)
            {
                // ------------------------------------------------
                // COMMAND: START (0x01)
                // ------------------------------------------------
                if (cmd == CMD_START)
                {
                    Mahjong_Generate_New_Layout(); // Initial Generation

                    tx_packet[0] = CMD_START;
                    uint8_t* game_ptr = Mahjong_Get_Board_State();
                    memcpy(&tx_packet[1], game_ptr, TOTAL_PIECES);
                    tx_packet[51] = Calc_CRC(tx_packet, 51);
                    HAL_UART_Transmit(&huart1, tx_packet, 52, 100);
                }

                // ------------------------------------------------
                // COMMAND: RESET (0x02)
                // ------------------------------------------------
                else if (cmd == CMD_RESET)
                {
                    cmd_reset(); // Call command_list logic

                    // Send Confirmation: [CMD] [0x00] [CRC]
                    tx_packet[0] = CMD_RESET;
                    tx_packet[1] = 0x00; // OK
                    tx_packet[2] = Calc_CRC(tx_packet, 2);
                    HAL_UART_Transmit(&huart1, tx_packet, 3, 100);
                }

                // ------------------------------------------------
                // COMMAND: SHUFFLE (0x03)
                // ------------------------------------------------
                else if (cmd == CMD_SHUFFLE)
                {
                    uint8_t status = cmd_shuffle(); // Returns 0x00 (OK) or 0xFF (Limit)

                    if (status == 0x00) {
                        // Send New Board State (52 bytes)
                        tx_packet[0] = CMD_SHUFFLE;
                        uint8_t* game_ptr = Mahjong_Get_Board_State();
                        memcpy(&tx_packet[1], game_ptr, TOTAL_PIECES);
                        tx_packet[51] = Calc_CRC(tx_packet, 51);
                        HAL_UART_Transmit(&huart1, tx_packet, 52, 100);
                    } else {
                        // Send Error: [CMD] [0xFF] [CRC]
                        tx_packet[0] = CMD_SHUFFLE;
                        tx_packet[1] = 0xFF;
                        tx_packet[2] = Calc_CRC(tx_packet, 2);
                        HAL_UART_Transmit(&huart1, tx_packet, 3, 100);
                    }
                }

                // ------------------------------------------------
                // COMMAND: SELECT (0x04)
                // ------------------------------------------------
                else if (cmd == CMD_SELECT)
                {
                    uint8_t status = cmd_select(data_byte);

                    tx_packet[0] = CMD_SELECT;
                    tx_packet[1] = status; // 0x00 OK, 0xFF Error
                    tx_packet[2] = Calc_CRC(tx_packet, 2);
                    HAL_UART_Transmit(&huart1, tx_packet, 3, 100);
                }

                // ------------------------------------------------
                // COMMAND: MATCH (0x05)
                // ------------------------------------------------
                else if (cmd == CMD_MATCH)
                {
                    uint8_t result = cmd_match(data_byte);

                    tx_packet[0] = CMD_MATCH;
                    tx_packet[1] = result; // 0x01 Match, 0x00 Fail
                    tx_packet[2] = Calc_CRC(tx_packet, 2);
                    HAL_UART_Transmit(&huart1, tx_packet, 3, 100);
                }
            }
            // Resume Listening
            HAL_UART_Receive_IT(&huart1, rx_packet, 3);
        }
    }
  /* USER CODE END 3 */
}

// ... [Rest of your SystemClock_Config and MX functions remain unchanged] ...
/**
 * TEST CLOCK
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
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

  /** Initializes the CPU, AHB and APB buses clocks
  */
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

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
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

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(G_LED_GPIO_Port, G_LED_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : G_LED_Pin */
  GPIO_InitStruct.Pin = G_LED_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(G_LED_GPIO_Port, &GPIO_InitStruct);
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  __disable_irq();
  while (1)
  {
  }
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  * where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
}
#endif /* USE_FULL_ASSERT */
