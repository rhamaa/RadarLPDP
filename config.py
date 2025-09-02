# config.py
import os

# --- Konfigurasi Aplikasi ---

# Tentukan direktori root proyek secara dinamis
# Ini adalah direktori tempat file main.py berada
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Konfigurasi Background Worker Eksternal ---
# Ubah nama/path exe di sini. Secara default hanya dijalankan di Windows.
# Di Linux/macOS, set only_on_platforms=[] dan sesuaikan exe_name (misal gunakan wine) jika ingin tetap dijalankan.
EXTERNAL_WORKER = {
    "enabled": True,
    "exe_name": "cadgetdataSave.exe",  # bisa nama file relatif atau path absolut
    "args": [],                         # contoh: ["--port", "9000"]
    "cwd": None,                        # None = otomatis ke direktori file exe
    "env": {},                          # tambahan environment variables
    "only_on_platforms": ["win32"],    # ganti ke [] untuk semua OS
}

# --- Konfigurasi Pemantauan File ---
# Nama file data yang akan dipantau. Path ini sekarang absolut dan andal.
FILENAME_BASE = "live/live_acquisition_ui.bin"
FILENAME = os.path.join(PROJECT_ROOT, FILENAME_BASE)

# Rate sampling data dari akuisisi (dalam Hz)
SAMPLE_RATE = 20_000_000  # 20 MHz

# Seberapa sering (dalam detik) memeriksa pembaruan file
POLLING_INTERVAL = 0.5  # Detik (sudah tidak digunakan oleh fft_worker)
WORKER_REFRESH_INTERVAL = 0.05 # Detik, untuk refresh UI ~20 FPSali per detik

# --- Pengaturan Serial Port ---
SERIAL_PORT = '/dev/ttyUSB0'  # Port untuk ESP32/Arduino
BAUD_RATE = 115200            # Harus sama dengan yang di kode Arduino
SERIAL_TIMEOUT = 1            # Timeout untuk pembacaan serial (dalam detik)

# --- Konfigurasi Tampilan ---
APP_SPACING = 8
APP_PADDING = 8

# Palet warna yang konsisten untuk tema aplikasi
THEME_COLORS = {
    "background": (21, 21, 21, 255),      # Latar belakang yang sangat gelap
    "scan_area": (37, 37, 38, 150),       # Area scan yang sedikit transparan
    "grid_lines": (255, 255, 255, 40),    # Garis putih yang sangat pudar
    "text": (255, 255, 255, 150),         # Teks putih yang tidak terlalu mencolok
    "accent": (0, 200, 119, 255),         # Warna hijau/teal untuk sapuan jarum
    "target": (255, 0, 0, 255),           # Merah terang untuk target
}
