<<<<<<< HEAD
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
SERIAL_PORT = 'COM9'  # Port untuk ESP32/Arduino
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
=======
"""Configuration module for Radar LPDP application.

This module contains all configuration constants and settings for the radar system,
including hardware parameters, file paths, and UI settings.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

# --- Project Paths ---

PROJECT_ROOT: Path = Path(__file__).parent.absolute()
"""Root directory of the project."""

# --- External Worker Configuration ---

EXTERNAL_WORKER: Dict[str, Any] = {
    "enabled": True,
    "exe_name": "cadgetdataSave.exe",
    "args": [],
    "cwd": None,
    "env": {},
    "only_on_platforms": ["win32"],
}
"""Configuration for external data acquisition worker.

Attributes:
    enabled: Whether to run the external worker
    exe_name: Name or path of the executable
    args: Command line arguments for the executable
    cwd: Working directory (None = auto-detect from exe location)
    env: Additional environment variables
    only_on_platforms: List of platforms to run on (e.g., ['win32'])
"""

# --- Data Acquisition Configuration ---

FILENAME_BASE: str = "live/live_acquisition_ui.bin"
"""Relative path to the live data file."""

FILENAME: str = str(PROJECT_ROOT / FILENAME_BASE)
"""Absolute path to the live data file."""

# Hardware Parameters
SAMPLE_RATE: int = 20_000_000
"""ADC sample rate in Hz (20 MHz)."""

BUFFER_SAMPLES: int = 8192
"""Number of samples per acquisition buffer."""

NUM_CHANNELS: int = 2
"""Number of ADC channels (CH1 and CH3)."""

# FFT Processing Configuration
FFT_SMOOTHING_ENABLED: bool = True
"""Enable FFT spectrum smoothing to reduce noise."""

FFT_SMOOTHING_WINDOW: int = 11
"""Moving average smoothing window (fallback for other methods)."""

FFT_SMOOTHING_METHOD: str = "savgol"
"""Smoothing method to apply ('moving_average' or 'savgol')."""

FFT_SAVGOL_WINDOW: int = 51
"""Savitzky-Golay window length (must be odd)."""

FFT_SAVGOL_POLYORDER: int = 3
"""Savitzky-Golay polynomial order."""

FFT_MAGNITUDE_MODE: str = "db"
"""Output magnitude scale for FFT ('linear' or 'db')."""

FFT_MAGNITUDE_FLOOR_DB: float = -105.0
"""Clamp FFT magnitude to this floor to suppress noise grass (dB)."""

# Worker Configuration
POLLING_INTERVAL: float = 0.5
"""File polling interval in seconds (deprecated, kept for compatibility)."""

WORKER_REFRESH_INTERVAL: float = 0.05
"""UI refresh interval in seconds (~20 FPS)."""

# Target Detection Configuration
TARGET_HISTORY_MAX_SIZE: int = 50
"""Maximum number of targets to keep in history."""

TARGET_FREQ_THRESHOLD_KHZ: float = 10_000.0
"""Frequency threshold for target detection in kHz (10 MHz)."""

FILTERED_EXTREMA_INDEX_THRESHOLD: int = 2000
"""FFT bin index threshold for filtered extrema analysis."""

# --- Serial Port Configuration ---

SERIAL_PORT: str = '/dev/ttyUSB0'
"""Serial port for ESP32/Arduino communication."""

BAUD_RATE: int = 115200
"""Serial baud rate (must match Arduino code)."""

SERIAL_TIMEOUT: float = 1.0
"""Serial read timeout in seconds."""

# --- UI Display Configuration ---

APP_SPACING: int = 8
"""Spacing between UI elements in pixels."""

APP_PADDING: int = 8
"""Padding for UI elements in pixels."""

# Color Theme
THEME_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    "background": (21, 21, 21, 255),
    "scan_area": (37, 37, 38, 150),
    "grid_lines": (255, 255, 255, 40),
    "text": (255, 255, 255, 150),
    "accent": (0, 200, 119, 255),
    "target": (255, 0, 0, 255),
}
"""Color palette for the application theme.

Colors are in RGBA format (Red, Green, Blue, Alpha).
"""

# --- Radar Configuration ---

RADAR_MAX_RANGE: float = 15.0
"""Maximum radar range in meters."""

RADAR_SWEEP_ANGLE_MIN: float = 0.0
"""Minimum sweep angle in degrees."""

RADAR_SWEEP_ANGLE_MAX: float = 180.0
"""Maximum sweep angle in degrees."""
>>>>>>> ecb4947d480b793a4e8317e42ddd693ce8163b2d
