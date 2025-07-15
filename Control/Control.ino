/*
 *  FreeRTOS – Derajat 0-180 berganti arah di limit-switch,
 *              kecepatan diatur rotary-switch.
 *  Board  : Arduino Mega 2560
 *  Library: Arduino_FreeRTOS_Library
 */
#include <Arduino_FreeRTOS.h>

/* ====== Pin map ====== */
const uint8_t PIN_LIMIT_RIGHT = 9;      // NO right
const uint8_t PIN_LIMIT_LEFT  = 10;     // NO left
const uint8_t ROTARY_PINS[]   = {12, 13, 14, 15, 16, 17};
const uint8_t ROTARY_COUNT    = sizeof(ROTARY_PINS);

/* ====== GLOBAL VAR ====== */
volatile int16_t  g_degree    = 0;      // 0-180°
volatile int8_t   g_direction = +1;     // +1 fwd, -1 rev
volatile uint16_t g_delayMs   = 1000;   // step interval (0 => stop)

/* ====== Task proto ====== */
void TaskMotion (void *pv);
void TaskRotary (void *pv);
void TaskLimit  (void *pv);

/* ====== Helper: protected write ====== */
void setDelayMs(uint16_t d) {
  taskENTER_CRITICAL();
  g_delayMs = d;
  taskEXIT_CRITICAL();
}
void setDirection(int8_t dir) {
  taskENTER_CRITICAL();
  g_direction = dir;
  taskEXIT_CRITICAL();
}

/* ====== SETUP ====== */
void setup() {
  Serial.begin(9600);

  pinMode(PIN_LIMIT_RIGHT, INPUT_PULLUP);
  pinMode(PIN_LIMIT_LEFT,  INPUT_PULLUP);
  for (uint8_t i = 0; i < ROTARY_COUNT; i++)
    pinMode(ROTARY_PINS[i], INPUT_PULLUP);

  /* ---- Create tasks ----                    Name  Stack  Arg  Prio */
  xTaskCreate(TaskMotion, "MOT", 128, nullptr, 2, nullptr);
  xTaskCreate(TaskRotary, "ROT", 128, nullptr, 3, nullptr);
  xTaskCreate(TaskLimit , "LIM",  96, nullptr, 4, nullptr);

  vTaskStartScheduler();   // kernel takes over
}
void loop() {}  // never used

/* ========= TASK: Motion =========
 * Naik-turunkan g_degree sesuai g_direction setiap g_delayMs.
 * Jika g_delayMs == 0  ➜ berhenti (poll tiap 100 ms).
 */
void TaskMotion(void *pv) {
  for (;;) {
    uint16_t delayCopy;
    int8_t   dirCopy;
    taskENTER_CRITICAL();
      delayCopy = g_delayMs;
      dirCopy   = g_direction;
    taskEXIT_CRITICAL();

    if (delayCopy == 0) {                // STOP
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }

    vTaskDelay(pdMS_TO_TICKS(delayCopy));

    taskENTER_CRITICAL();
      g_degree += dirCopy;
      if (g_degree < 0)   g_degree = 0;
      if (g_degree > 180) g_degree = 180;
      /* salin untuk printing di luar critical */
      int16_t dNow  = g_degree;
      int8_t  dirNow= g_direction;
      uint16_t spd  = g_delayMs;
    taskEXIT_CRITICAL();

    Serial.print(F("Deg: "));
    Serial.print(dNow);
    Serial.print(F("  Dir: "));
    Serial.print(dirNow == 1 ? '>' : '<');
    Serial.print(F("  Delay(ms): "));
    Serial.println(spd);
  }
}

/* ========= TASK: Rotary =========
 * Baca posisi rotary, atur g_delayMs.
 * Mapping: {0,1000,2000,3000,4000,5000}
 */
void TaskRotary(void *pv) {
  const uint16_t DELAY_MAP[] = {0, 1000, 2000, 3000, 4000, 5000};
  uint8_t lastPos = 255;
  const TickType_t period = pdMS_TO_TICKS(50);

  for (;;) {
    uint8_t pos = 255;
    for (uint8_t i = 0; i < ROTARY_COUNT; i++)
      if (digitalRead(ROTARY_PINS[i]) == LOW) { pos = i; break; } // 0-5

    if (pos != 255 && pos != lastPos) {
      setDelayMs(DELAY_MAP[pos]);
      Serial.print(F("Speed set via rotary: "));
      Serial.println(DELAY_MAP[pos]);
      lastPos = pos;
    }
    vTaskDelay(period);
  }
}

/* ========= TASK: Limit =========
 * Ubah arah bila saklar limit LOW.
 */
void TaskLimit(void *pv) {
  bool lastR = digitalRead(PIN_LIMIT_RIGHT);
  bool lastL = digitalRead(PIN_LIMIT_LEFT);
  const TickType_t period = pdMS_TO_TICKS(20);

  for (;;) {
    bool r = digitalRead(PIN_LIMIT_RIGHT);
    bool l = digitalRead(PIN_LIMIT_LEFT);

    if (r != lastR) {
      Serial.println(r == LOW ? F("RIGHT TRIGGER") : F("RIGHT release"));
      if (r == LOW) setDirection(+1);    // maju 0➜180
      lastR = r;
    }
    if (l != lastL) {
      Serial.println(l == LOW ? F("LEFT TRIGGER") : F("LEFT release"));
      if (l == LOW) setDirection(-1);    // mundur 180➜0
      lastL = l;
    }
    vTaskDelay(period);
  }
}
