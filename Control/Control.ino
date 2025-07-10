// ESP32 Serial Angle Sender

// Variabel untuk mengontrol kecepatan sapuan.
// Nilai yang lebih kecil berarti sapuan lebih cepat.
int sweep_delay = 200; // dalam milidetik

int angle = 0;
int direction = 1; // 1 untuk maju (0 -> 180), -1 untuk mundur (180 -> 0)

void setup() {
  // Mulai komunikasi serial dengan baud rate 115200
  Serial.begin(115200);
}

void loop() {
  // Kirim nilai sudut saat ini melalui serial, diakhiri dengan newline
  Serial.println(angle);

  // Update sudut untuk langkah berikutnya
  angle = angle + direction;

  // Jika sudut mencapai batas, balikkan arahnya
  if (angle >= 180) {
    direction = -1;
    angle = 180; // Pastikan tidak melebihi batas
  } else if (angle <= 0) {
    direction = 1;
    angle = 0; // Pastikan tidak kurang dari batas
  }

  // Tunggu sejenak untuk mengontrol kecepatan
  delay(sweep_delay);
}