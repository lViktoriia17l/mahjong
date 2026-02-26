/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "mahjong.h"
#include <stdlib.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
TIM_HandleTypeDef htim2;

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
static void MX_TIM2_Init(void);
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

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
    // Check if the interrupt came from TIM2
    if (htim->Instance == TIM2) {
        Timer_Tick(); // Increment our game seconds
    }
}

/* --------- UART RX callback (Interrupt) --------- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        packet_ready = 1;
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

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART1_UART_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */

  Mahjong_Init();
  srand(HAL_GetTick());

  // Start the timer interrupt
  HAL_TIM_Base_Start_IT(&htim2);

  // Start listening for the first 3-byte command
  HAL_UART_Receive_IT(&huart1, rx_packet, 3);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    if (packet_ready) {
        uint8_t cmd = rx_packet[0];
        uint8_t data = rx_packet[1];
        uint8_t received_crc = rx_packet[2];

        uint8_t calculated_crc = Calc_CRC(rx_packet, 2);

        if (calculated_crc == received_crc) {

            memset(tx_packet, 0, sizeof(tx_packet));
            tx_packet[0] = cmd;

            switch (cmd) {
                case CMD_START:
                    Mahjong_Generate_New_Layout();
                    Timer_Start(); // Start the game clock
                    memcpy(&tx_packet[1], Mahjong_Get_Board_State(), 50);
                    break;

                case CMD_RESET:
                    cmd_reset();
                    break;

                case CMD_SHUFFLE: {
                    uint8_t res = cmd_shuffle();
                    if (res == 0xFF) {
                        tx_packet[1] = 0xFF; // Limit reached
                    } else {
                        memcpy(&tx_packet[1], Mahjong_Get_Board_State(), 50);
                    }
                    break;
                }

                case CMD_SELECT:
                    tx_packet[1] = cmd_select(data);
                    break;

                case CMD_MATCH:
                    tx_packet[1] = cmd_match(data);
                    break;

                case CMD_GIVE_UP:
                    cmd_give_up();
                    break;

                case CMD_HINT: {
                    uint8_t idx1, idx2;
                    if (cmd_hint(&idx1, &idx2)) {
                        tx_packet[1] = idx1;
                        tx_packet[2] = idx2;
                    } else {
                        tx_packet[1] = 100; // No pairs left
                    }
                    break;
                }

                case CMD_GET_TIME: {
                    uint32_t elapsed = Timer_GetSeconds();
                    // Split 32-bit integer into 4 bytes (Big Endian)
                    tx_packet[1] = (elapsed >> 24) & 0xFF;
                    tx_packet[2] = (elapsed >> 16) & 0xFF;
                    tx_packet[3] = (elapsed >> 8) & 0xFF;
                    tx_packet[4] = elapsed & 0xFF;
                    break;
                }
            }

            // Calculate outgoing CRC (over first 51 bytes)
            tx_packet[51] = Calc_CRC(tx_packet, 51);

            // Determine transmit length based on command type to match Python expectation
            // Python's CMD_START and CMD_SHUFFLE and CMD_GET_TIME expect 52 bytes
            if (cmd == CMD_START || cmd == CMD_SHUFFLE || cmd == CMD_GET_TIME) {
                HAL_UART_Transmit(&huart1, tx_packet, 52, 100);
            }
            // CMD_HINT expects 4 bytes
            else if (cmd == CMD_HINT) {
                tx_packet[3] = Calc_CRC(tx_packet, 3);
                HAL_UART_Transmit(&huart1, tx_packet, 4, 100);
            }
            // All other commands expect 3 bytes
            else {
                tx_packet[2] = Calc_CRC(tx_packet, 2);
                HAL_UART_Transmit(&huart1, tx_packet, 3, 100);
            }
        }

        // Reset flag and re-enable interrupt to catch next command
        packet_ready = 0;
        HAL_UART_Receive_IT(&huart1, rx_packet, 3);
    }
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
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

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  // Based on 48MHz System Clock. 48MHz / 48000 = 1000 Hz. 1000 / 1000 = 1 Hz (1 Second)
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
  /* USER CODE BEGIN TIM2_Init 2 */
  /* Enable the TIM2 global Interrupt in the NVIC */
  HAL_NVIC_SetPriority(TIM2_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(TIM2_IRQn);
  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200; // Updated to match Python script
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
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

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

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {

        // 1. Clear the hardware error flags
        __HAL_UART_CLEAR_OREFLAG(huart); // Overrun
        __HAL_UART_CLEAR_NEFLAG(huart);  // Noise
        __HAL_UART_CLEAR_FEFLAG(huart);  // Framing

        // 2. Restart the interrupt listener to catch the next 3 bytes safely
        packet_ready = 0;
        HAL_UART_Receive_IT(&huart1, rx_packet, 3);
    }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
