# functions/data_processing.py

import numpy as np
import threading
import queue
import struct
import os
import time
import math
import collections
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks, get_window
from scipy import stats as sp_stats

# Impor konfigurasi terpusat
from config import FILENAME, SAMPLE_RATE, WORKER_REFRESH_INTERVAL, SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT
import serial # Tambahkan impor untuk komunikasi serial

# --- Helper Functions --- #

def (center_x, center_y, angle_deg, radius):
    """Konversi koordinat polar ke Cartesian."""
    angle_rad = math.radians(angle_deg)
    return center_x + radius * math.cos(angle_rad), center_y + radius * math.sin(angle_rad)

def load_and_process_data(filepath, sr):
    """Memuat data dari file biner, memisahkan channel, dan menghapus DC offset."""
    try:
        if not os.path.exists(filepath):
            return None, None, None, None

        with open(filepath, "rb") as f:
            data = f.read()
        
        if not data: # Jika file kosong
            return np.array([]), np.array([]), 0, sr

        # Pastikan panjang byte genap (kelipatan 2) untuk unpack uint16
        if (len(data) % 2) != 0:
            # Truncate 1 byte terakhir yang tidak lengkap
            data = data[:-1]

        values = np.array(struct.unpack(f"<{len(data)//2}H", data), dtype=np.float32)

        # Pastikan jumlah sampel 16-bit genap agar bisa dipetakan ke 2 channel (CH1, CH2)
        if (len(values) % 2) != 0:
            values = values[:-1]
        ch1 = values[::2]
        ch2 = values[1::2]
        ch1 -= np.mean(ch1)
        ch2 -= np.mean(ch2)
        return ch1, ch2, len(ch1), sr
    except Exception as e:
        print(f"Error reading or processing file {filepath}: {e}")
        return None, None, None, None

def compute_fft(channel, sample_rate, window: str = "hann"):
    """Menghitung spektrum dengan SciPy (rFFT) dan mengonversi magnitudo ke dB.
    - Gunakan jendela (default Hann) untuk mengurangi spectral leakage.
    - Kembalikan frekuensi dalam kHz dan magnitude dalam dB.
    """
    n = len(channel)
    if n == 0:
        return np.array([]), np.array([])

    x = np.asarray(channel, dtype=float)
    if window:
        try:
            w = get_window(window, n, fftbins=True)
            x = x * w
        except Exception:
            # Fallback tanpa window jika nama window tidak valid
            pass

    # Real FFT untuk sinyal real → hanya sisi positif (n//2+1)
    Y = rfft(x)
    magnitudes = np.abs(Y)

    # Konversi ke dB, hindari log(0)
    magnitudes_db = 20.0 * np.log10(magnitudes + 1e-12)

    # Frekuensi dalam kHz
    frequencies_khz = rfftfreq(n, d=1.0 / sample_rate) / 1000.0
    return frequencies_khz, magnitudes_db

def find_peak_metrics(frequencies, magnitudes):
    """Menemukan frekuensi dan magnitudo puncak dari data FFT."""
    if len(magnitudes) == 0:
        return 0, 0
    peak_index = np.argmax(magnitudes)
    peak_freq = frequencies[peak_index]
    peak_mag = magnitudes[peak_index]
    return peak_freq, peak_mag

def find_top_extrema(frequencies, magnitudes, n_extrema=3, prominence_db=3.0, distance_bins=1):
    """Menemukan beberapa puncak (peaks) dan lembah (valleys) teratas pada spektrum.

    Parameters
    - frequencies: array frekuensi (dalam kHz) hasil dari compute_fft
    - magnitudes: array magnitudo dalam dB (hasil dari compute_fft)
    - n_extrema: berapa banyak puncak/lembah teratas yang ingin diambil
    - prominence_db: ambang prominence untuk deteksi puncak/lembah (dalam dB)
    - distance_bins: jarak minimum antar puncak (dalam indeks bin FFT)

    Returns
    - peaks: list of dict {"index", "freq_khz", "mag_db"}
    - valleys: list of dict {"index", "freq_khz", "mag_db"}
    """
    if len(magnitudes) == 0:
        return [], []

    # Temukan puncak pada magnitudo dB
    peak_idx, peak_props = find_peaks(magnitudes, prominence=prominence_db, distance=distance_bins)
    # Urutkan puncak berdasarkan magnitudo tertinggi
    peak_idx_sorted = sorted(peak_idx, key=lambda i: magnitudes[i], reverse=True)[:n_extrema]
    peaks = [
        {"index": int(i), "freq_khz": float(frequencies[i]), "mag_db": float(magnitudes[i])}
        for i in peak_idx_sorted
    ]

    # Temukan lembah dengan mencari puncak pada sinyal terbalik
    inv = -magnitudes
    valley_idx, valley_props = find_peaks(inv, prominence=prominence_db, distance=distance_bins)
    # Urutkan lembah berdasarkan kedalaman (magnitudo paling rendah)
    valley_idx_sorted = sorted(valley_idx, key=lambda i: magnitudes[i])[:n_extrema]
    valleys = [
        {"index": int(i), "freq_khz": float(frequencies[i]), "mag_db": float(magnitudes[i])}
        for i in valley_idx_sorted
    ]

    return peaks, valleys

# --- Helper Functions for Workers --- #

def compute_basic_stats(arr: np.ndarray) -> dict:
    """Hitung statistik dasar menggunakan SciPy untuk konsistensi.
    - mean, variance, min, max dari scipy.stats.describe
    - std = sqrt(variance)
    - rms menggunakan NumPy (tidak ada helper langsung di SciPy)
    """
    if arr is None or len(arr) == 0:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "rms": 0.0}
    desc = sp_stats.describe(np.asarray(arr, dtype=float), ddof=0)
    mean = float(desc.mean)
    var = float(desc.variance) if desc.variance is not None else float(np.var(arr))
    std = float(np.sqrt(var))
    min_val, max_val = map(float, desc.minmax)
    rms = float(np.sqrt(np.mean(np.square(arr))))
    return {"mean": mean, "std": std, "min": min_val, "max": max_val, "rms": rms}

def compute_fft_analysis(channel: np.ndarray, sample_rate: float,
                         n_extrema: int = 5, prominence_db: float = 3.0, distance_bins: int = 10) -> dict:
    """Pembungkus analisis FFT satu channel: frekuensi, magnitudo dB, top peaks/valleys, dan puncak maksimum."""
    n = len(channel) if channel is not None else 0
    if n == 0:
        return {
            "frequencies": np.array([]),
            "magnitudes": np.array([]),
            "peak_frequencies": np.array([]),
            "peak_magnitudes": np.array([]),
            "max_freq": 0.0,
            "max_mag": 0.0,
        }

    freqs_khz, mags_db = compute_fft(channel, sample_rate)
    peaks, valleys = find_top_extrema(freqs_khz, mags_db, n_extrema=n_extrema,
                                      prominence_db=prominence_db, distance_bins=distance_bins)
    peak_freq, peak_mag = find_peak_metrics(freqs_khz, mags_db)

    return {
        "frequencies": np.ascontiguousarray(freqs_khz, dtype=np.float64),
        "magnitudes": np.ascontiguousarray(mags_db, dtype=np.float64),
        "peak_frequencies": np.ascontiguousarray([p["freq_khz"] for p in peaks], dtype=np.float64),
        "peak_magnitudes": np.ascontiguousarray([p["mag_db"] for p in peaks], dtype=np.float64),
        "peak_indices": np.ascontiguousarray([p["index"] for p in peaks], dtype=np.int32),
        "max_freq": float(peak_freq),
        "max_mag": float(peak_mag),
    }

def generate_time_axis_s(n_samples: int, sample_rate: float) -> np.ndarray:
    """Bangun sumbu waktu dalam detik (float64, C-contiguous)."""
    if n_samples <= 0 or sample_rate <= 0:
        return np.array([], dtype=np.float64)
    return np.ascontiguousarray(np.linspace(0, n_samples / sample_rate, n_samples, endpoint=False), dtype=np.float64)

def analyze_loaded_data(ch1: np.ndarray, ch2: np.ndarray, sample_rate: float,
                        n_samples: int | None = None, duration_s: float | None = None) -> dict:
    """Analisis lengkap dua channel yang sudah dimuat (FFT + statistik) dan info file."""
    ch1_fft = compute_fft_analysis(ch1, sample_rate)
    ch2_fft = compute_fft_analysis(ch2, sample_rate)
    ch1_stats = compute_basic_stats(ch1)
    ch2_stats = compute_basic_stats(ch2)
    if n_samples is None:
        n_samples = len(ch1) if ch1 is not None else 0
    if duration_s is None and sample_rate > 0:
        duration_s = n_samples / sample_rate
    return {
        "ch1_fft": ch1_fft,
        "ch2_fft": ch2_fft,
        "ch1_stats": ch1_stats,
        "ch2_stats": ch2_stats,
        "file_info": {
            "duration": float(duration_s or 0.0),
            "n_samples": int(n_samples or 0),
            "sample_rate": float(sample_rate or 0.0),
        },
    }

def load_file_and_prepare(filepath: str, sample_rate: float) -> tuple[dict | None, str | None]:
    """Memuat file biner dan menyiapkan struktur data standar untuk UI popup.
    Return (data_dict, error_msg).
    """
    ch1_data, ch2_data, n_samples, sr = load_and_process_data(filepath, sample_rate)
    if ch1_data is None or n_samples is None or n_samples <= 0:
        return None, "File tidak ditemukan atau kosong"
    time_axis = generate_time_axis_s(n_samples, sr)
    return {
        "ch1": np.ascontiguousarray(ch1_data, dtype=np.float64),
        "ch2": np.ascontiguousarray(ch2_data, dtype=np.float64),
        "time_axis": time_axis,
        "n_samples": n_samples,
        "sample_rate": sr,
        "duration": (n_samples / sr) if sr else 0.0,
    }, None

def process_channel_data(filepath, sr):
    """Memuat data dari file, memproses FFT, dan mengembalikan hasilnya."""
    ch1_data, ch2_data, n_samples, _ = load_and_process_data(filepath, sr)
    if ch1_data is None or n_samples <= 0:
        return None, None

    freqs_ch1, mag_ch1 = compute_fft(ch1_data, sr)
    freqs_ch2, mag_ch2 = compute_fft(ch2_data, sr)
    peak_freq_ch1, peak_mag_ch1 = find_peak_metrics(freqs_ch1, mag_ch1)
    peak_freq_ch2, peak_mag_ch2 = find_peak_metrics(freqs_ch2, mag_ch2)

    # Ekstrak beberapa puncak dan lembah teratas beserta indeks bin-nya
    ch1_peaks, ch1_valleys = find_top_extrema(freqs_ch1, mag_ch1, n_extrema=5, prominence_db=3.0, distance_bins=1)
    ch2_peaks, ch2_valleys = find_top_extrema(freqs_ch2, mag_ch2, n_extrema=5, prominence_db=3.0, distance_bins=1)

    fft_result = {
        "status": "done",
        "freqs_ch1": freqs_ch1, "mag_ch1": mag_ch1,
        "freqs_ch2": freqs_ch2, "mag_ch2": mag_ch2,
        "n_samples": n_samples, "sample_rate": sr,
        "metrics": {
            "ch1": {
                "peak_freq": peak_freq_ch1, "peak_mag": peak_mag_ch1,
                "peaks": ch1_peaks, "valleys": ch1_valleys
            },
            "ch2": {
                "peak_freq": peak_freq_ch2, "peak_mag": peak_mag_ch2,
                "peaks": ch2_peaks, "valleys": ch2_valleys
            }
        }
    }
    return fft_result, fft_result["metrics"]

def calculate_target_distance(metrics):
    """Menghitung jarak target berdasarkan metrik puncak dari kedua channel."""
    if not metrics:
        return None
    
    # Ambil metrik dari kedua channel
    val_ch1 = metrics["ch1"]["peak_freq"] * metrics["ch1"]["peak_mag"]
    val_ch2 = metrics["ch2"]["peak_freq"] * metrics["ch2"]["peak_mag"]
    
    # Gabungkan nilai dari kedua channel dan bagi dengan 1000 (2 * 500)
    distance = (val_ch1 + val_ch2) / 1000
    
    if distance > 1:
        return min(distance, 15) # Kembalikan jarak yang sudah di-clamp
    return None

def update_sweep_angle(current_angle, direction, increment):
    """Memperbarui sudut sapuan untuk gerakan bolak-balik 180 derajat."""
    new_angle = current_angle + increment * direction
    if not (0 <= new_angle <= 180):
        direction *= -1
        new_angle = np.clip(new_angle, 0, 180)
    return new_angle, direction

# --- Worker Thread Functions --- #

def angle_worker(ppi_queue: queue.Queue, stop_event: threading.Event):
    """Membaca data sudut dari port serial, melakukan sinkronisasi arah, dan
    mengirim sudut 0-180° terkalibrasi ke antrian PPI.
    """

    # --- State for synchronization ---
    prev_raw = None          # sudut mentah terakhir yang diterima
    prev_dir = None          # +1 (naik) atau -1 (turun)
    base_offset = 0.0        # sudut mentah yang dipetakan ke 0°/180°
    EPS_MOVEMENT = 1e-3      # ambang pergerakan (deg) untuk deteksi berhenti

    while not stop_event.is_set():
        try:
            # Coba buka port serial
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT) as ser:
                print(f"Berhasil terhubung ke port serial {SERIAL_PORT}")
                while not stop_event.is_set():
                    if ser.in_waiting > 0:
                        try:
                            # Baca satu baris dari serial, hilangkan whitespace, dan decode
                            line = ser.readline().strip()
                            if not line:
                                continue

                            angle_str = line.decode('utf-8')
                            # Konversi langsung ke float untuk mendukung nilai desimal (mis. 45.7)
                            angle = float(angle_str)
                            
                            # --- Sinkronisasi & translasi sudut ---
                            if prev_raw is None:
                                # Pembacaan pertama → jadikan baseline
                                base_offset = angle
                                prev_raw = angle
                                prev_dir = None
                                ui_angle = 0.0
                                ppi_queue.put({"type": "sweep", "angle": ui_angle})
                                continue

                            delta = angle - prev_raw
                            if abs(delta) < EPS_MOVEMENT:
                                # nyaris tidak bergerak, abaikan
                                prev_raw = angle
                                continue

                            curr_dir = 1 if delta > 0 else -1

                            # Deteksi pergantian arah
                            if prev_dir is None:
                                prev_dir = curr_dir
                                base_offset = angle
                            elif curr_dir != prev_dir:
                                # Limit switch terpencet → reset baseline
                                prev_dir = curr_dir
                                base_offset = angle

                            # Translasi ke 0-180 berdasarkan arah
                            if curr_dir == 1:
                                # raw naik ⇒ UI 0→180
                                ui_angle = angle - base_offset  # start 0 increasing
                            else:
                                # raw turun ⇒ UI 180→0
                                ui_angle = 180 - (base_offset - angle)  # start 180 decreasing

                            # Clamp ke rentang valid UI
                            ui_angle = max(0.0, min(180.0, ui_angle))

                            ppi_queue.put({"type": "sweep", "angle": ui_angle})
                            prev_raw = angle

                        except ValueError:
                            print(f"Gagal mengonversi data serial ke angka: '{line.decode('utf-8', errors='ignore')}'")
                        except Exception as read_e:
                            print(f"Error saat membaca data serial: {read_e}")
        
        except serial.SerialException:
            print(f"Gagal terhubung ke {SERIAL_PORT}. Periksa koneksi. Mencoba lagi dalam 5 detik...")
            time.sleep(5)
        except Exception as e:
            print(f"Error tak terduga di angle_worker: {e}")
            time.sleep(5)

def fft_data_worker(fft_queue: queue.Queue, ppi_queue: queue.Queue, stop_event: threading.Event):
    """Memonitor file, menghitung FFT & metrik, menghitung jarak target, dan mengirim data ke antrian FFT & PPI."""
    last_modified_time = 0
    filepath = FILENAME
    sr = SAMPLE_RATE
    
    last_modified_time = 0
    filepath = FILENAME
    sr = SAMPLE_RATE

    while not stop_event.is_set():
        try:
            if os.path.exists(filepath):
                modified_time = os.path.getmtime(filepath)
                if modified_time != last_modified_time:
                    last_modified_time = modified_time
                    fft_queue.put({"status": "processing"})
                    
                    fft_result, metrics = process_channel_data(filepath, sr)
                    if fft_result:
                        fft_queue.put(fft_result)
                        
                        distance = calculate_target_distance(metrics)
                        if distance:
                            # Kirim event deteksi target TANPA informasi sudut
                            ppi_queue.put({"type": "target", "distance": distance})
            
            # Worker ini sekarang hanya tidur sebentar untuk tidak membebani CPU
            time.sleep(0.1)

        except Exception as e:
            print(f"Error in fft_data_worker: {e}")

def sinewave_data_worker(result_queue: queue.Queue, stop_event: threading.Event):
    """Memonitor file data untuk plot sinewave."""
    last_modified_time = 0
    filepath = FILENAME
    sr = SAMPLE_RATE

    while not stop_event.is_set():
        try:
            if os.path.exists(filepath):
                modified_time = os.path.getmtime(filepath)
                if modified_time != last_modified_time:
                    last_modified_time = modified_time
                    
                    ch1_data, ch2_data, n_samples, _ = load_and_process_data(filepath, sr)
                    if ch1_data is None or n_samples == 0:
                        continue
                    
                    # Konversi sumbu waktu ke mikrodetik (µs)
                    time_axis_us = np.linspace(0, n_samples / sr, n_samples, endpoint=False) * 1e6
                    
                    result_data = {
                        "status": "done",
                        "time_axis": time_axis_us,
                        "ch1_data": ch1_data,
                        "ch2_data": ch2_data
                    }
                    result_queue.put(result_data)

        except Exception as e:
            print(f"Error in sinewave_data_worker: {e}")
        
        # Gunakan interval refresh yang konsisten untuk menghindari NameError
        time.sleep(WORKER_REFRESH_INTERVAL)
