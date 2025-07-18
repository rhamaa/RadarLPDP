// Motor control with rotary switch, limit switches, and encoder feedback
// -------------------------------------------------------------------
// Include Encoder library (built‑in to most Arduino installs via Library Manager)
#include <Encoder.h>

// ------------------- Pin Assignments --------------------
#define RPWM 5         // PWM pin for forward
#define LPWM 6         // PWM pin for reverse
#define R_EN 7         // Enable forward
#define L_EN 8         // Enable reverse
#define LIMIT_RIGHT 9  // Right limit switch (active‑low)
#define LIMIT_LEFT 10  // Left  limit switch (active‑low)

// Encoder pins (interrupt capable on Uno/Nano: 2 & 3)
#define ENC_PIN_A 2
#define ENC_PIN_B 3

// Rotary switch pins (active‑low)
const int switchPins[6] = {12, 13, 14, 15, 16, 17};

// -------------------- Encoder setup ---------------------
Encoder motorEncoder(ENC_PIN_A, ENC_PIN_B);
const float COUNTS_PER_REV = 1024.0;        // ⚠️ Edit sesuai encoder kamu
const float WHEEL_DIAMETER_M = 0.10;        // 10 cm roda (opsional)
const float WHEEL_CIRC       = WHEEL_DIAMETER_M * PI;

// -------------------- Globals ---------------------------
int  lastRotaryPos = -1;        // Last rotary switch pos (1‑6)
int  motorSpeed    = 0;         // PWM duty (0‑255)
bool direction     = true;      // true = forward, false = reverse

long lastCount     = 0;         // For RPM calculation
unsigned long lastPrint = 0;    // Last time we printed encoder info
const unsigned long PRINT_INTERVAL = 200; // ms

// ------------------- Encoder helpers --------------------
long getEncoderCounts() {
  return motorEncoder.read();
}

void resetEncoderCounts() {
  motorEncoder.write(0);
}

bool getEncoderDirection(long deltaCounts) {
  return (deltaCounts >= 0);   // true = CW/forward
}

float countsToAngle(long counts) {
  return (counts % (long)COUNTS_PER_REV) * 360.0 / COUNTS_PER_REV;
}

float countsToDistance(long counts) {
  return (counts / COUNTS_PER_REV) * WHEEL_CIRC; // meters
}

float computeRPM(long deltaCounts, unsigned long deltaMillis) {
  if (deltaMillis == 0) return 0.0;
  return (deltaCounts * 60000.0) / (COUNTS_PER_REV * deltaMillis);
}

void printEncoderInfo() {
  unsigned long now = millis();
  if (now - lastPrint < PRINT_INTERVAL) return; // print setiap 200 ms

  long counts      = getEncoderCounts();
  long deltaCounts = counts - lastCount;
  unsigned long deltaMillis = now - lastPrint;
  float rpm        = computeRPM(deltaCounts, deltaMillis);
  bool dirCW       = getEncoderDirection(deltaCounts);
  float angleDeg   = countsToAngle(counts);
  float distanceM  = countsToDistance(counts);
  float speedMS    = (rpm * WHEEL_CIRC) / 60.0; // m/s

  Serial.print("Counts: ");   Serial.print(counts);
  Serial.print(" | Dir: ");   Serial.print(dirCW ? "CW" : "CCW");
  Serial.print(" | Angle: "); Serial.print(angleDeg, 1); Serial.print(" deg");
  Serial.print(" | RPM: ");   Serial.print(rpm, 1);
  Serial.print(" | Speed: "); Serial.print(speedMS, 3); Serial.print(" m/s");
  Serial.print(" | Dist: ");  Serial.print(distanceM, 3); Serial.println(" m");

  lastCount = counts;
  lastPrint = now;
}

// -------------------- Arduino setup ---------------------
void setup() {
  Serial.begin(9600);

  pinMode(RPWM, OUTPUT);
  pinMode(LPWM, OUTPUT);
  pinMode(R_EN, OUTPUT);
  pinMode(L_EN, OUTPUT);
  pinMode(LIMIT_RIGHT, INPUT_PULLUP);
  pinMode(LIMIT_LEFT,  INPUT_PULLUP);

  digitalWrite(R_EN, HIGH); // enable H‑bridge
  digitalWrite(L_EN, HIGH);

  for (int i = 0; i < 6; i++) {
    pinMode(switchPins[i], INPUT_PULLUP);
  }

  resetEncoderCounts();
}

// --------------------- Main loop ------------------------
void loop() {
  // ----- 1. Baca rotary switch speed setting -----
  int currentPosition = -1;
  for (int i = 0; i < 6; i++) {
    if (digitalRead(switchPins[i]) == LOW) { // aktif‑low
      currentPosition = i + 1;
      delay(50); // debounce sederhana
    }
  }

  if (currentPosition != -1 && currentPosition != lastRotaryPos) {
    Serial.print("Rotary Pos: ");
    Serial.println(currentPosition);
    lastRotaryPos = currentPosition;
  }

  if (currentPosition > 1) {
    motorSpeed = currentPosition * 5; // 2×5=10 dst (0‑255)
  } else {
    motorSpeed = 0; // posisi 1 = stop
  }
  motorSpeed = constrain(motorSpeed, 0, 255);

  // ----- 2. Limit switch (ubah arah otomatis) -----
  if (digitalRead(LIMIT_RIGHT) == LOW) direction = false; // sentuh kanan → reverse
  if (digitalRead(LIMIT_LEFT)  == LOW) direction = true;  // sentuh kiri  → forward

  // ----- 3. Drive motor -----
  if (motorSpeed == 0) {
    analogWrite(RPWM, 0);
    analogWrite(LPWM, 0);
  } else if (direction) {
    analogWrite(RPWM, motorSpeed);
    analogWrite(LPWM, 0);
  } else {
    analogWrite(RPWM, 0);
    analogWrite(LPWM, motorSpeed);
  }

  // ----- 4. Cetak data encoder -----
  printEncoderInfo();
}
