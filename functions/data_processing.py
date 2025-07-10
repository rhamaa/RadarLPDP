# functions/data_processing.py

import numpy as np
import threading
import queue
import struct
import os
import time
import math
import collections
from scipy.fft import fft, fftfreq

# Impor konfigurasi terpusat
from config import FILENAME, SAMPLE_RATE, WORKER_REFRESH_INTERVAL, SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT
import serial # Tambahkan impor untuk komunikasi serial

# --- Helper Functions --- #

def polar_to_cartesian(center_x, center_y, angle_deg, radius):
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

        values = np.array(struct.unpack(f"<{len(data)//2}H", data), dtype=np.float32)
        ch1 = values[::2]
        ch2 = values[1::2]
        ch1 -= np.mean(ch1)
        ch2 -= np.mean(ch2)
        return ch1, ch2, len(ch1), sr
    except Exception as e:
        print(f"Error reading or processing file {filepath}: {e}")
        return None, None, None, None

def compute_fft(channel, sample_rate):
    """Menghitung FFT dan mengonversi magnitudo ke dB."""
    n = len(channel)
    if n == 0:
        return np.array([]), np.array([])
    
    fft_vals = fft(channel)
    magnitudes = np.abs(fft_vals)[:n//2]
    
    # Konversi ke dB, hindari log(0) dengan menambahkan nilai epsilon kecil
    magnitudes_db = 20 * np.log10(magnitudes + 1e-9)
    
    # Hitung frekuensi dan konversi ke KHz
    frequencies_khz = fftfreq(n, d=1/sample_rate)[:n//2] / 1000
    return frequencies_khz, magnitudes_db

def find_peak_metrics(frequencies, magnitudes):
    """Menemukan frekuensi dan magnitudo puncak dari data FFT."""
    if len(magnitudes) == 0:
        return 0, 0
    peak_index = np.argmax(magnitudes)
    peak_freq = frequencies[peak_index]
    peak_mag = magnitudes[peak_index]
    return peak_freq, peak_mag

# --- Helper Functions for Workers ---

def process_channel_data(filepath, sr):
    """Memuat data dari file, memproses FFT, dan mengembalikan hasilnya."""
    ch1_data, ch2_data, n_samples, _ = load_and_process_data(filepath, sr)
    if ch1_data is None or n_samples <= 0:
        return None, None

    freqs_ch1, mag_ch1 = compute_fft(ch1_data, sr)
    freqs_ch2, mag_ch2 = compute_fft(ch2_data, sr)
    peak_freq_ch1, peak_mag_ch1 = find_peak_metrics(freqs_ch1, mag_ch1)
    peak_freq_ch2, peak_mag_ch2 = find_peak_metrics(freqs_ch2, mag_ch2)

    fft_result = {
        "status": "done",
        "freqs_ch1": freqs_ch1, "mag_ch1": mag_ch1,
        "freqs_ch2": freqs_ch2, "mag_ch2": mag_ch2,
        "n_samples": n_samples, "sample_rate": sr,
        "metrics": {
            "ch1": {"peak_freq": peak_freq_ch1, "peak_mag": peak_mag_ch1},
            "ch2": {"peak_freq": peak_freq_ch2, "peak_mag": peak_mag_ch2}
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
        return min(distance, 50) # Kembalikan jarak yang sudah di-clamp
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
    """Membaca data sudut dari port serial dan mengirimkannya ke antrian PPI."""
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
                            angle = int(float(angle_str)) # Konversi ke float dulu untuk menangani angka seperti "180.0"
                            
                            # Validasi rentang sudut
                            if 0 <= angle <= 180:
                                ppi_queue.put({"type": "sweep", "angle": angle})
                            else:
                                print(f"Data sudut di luar rentang diterima: {angle}")

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
