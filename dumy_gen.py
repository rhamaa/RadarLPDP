import numpy as np
import struct
import time
import os

FILENAME = "live/live_acquisition_ui.bin"

# Pastikan direktori .live ada
os.makedirs(os.path.dirname(FILENAME), exist_ok=True)
SAMPLE_RATE = 20_000_000
NUM_SAMPLES = 8192  # Jumlah sampel per channel

# Konfigurasi frekuensi (dalam Hz)
CH1_BASE_FREQ = 900_000
CH1_JITTER = 1_000
CH2_BASE_FREQ = 1_500_000
CH2_JITTER = 2_000

print(f"Starting simulation. Writing to '{FILENAME}' every 2 seconds.")
print("Run main.py in another terminal to see the live updates.")
print("Press Ctrl+C to stop.")

try:
    while True:
        # Buat sinyal gabungan dengan frekuensi yang sedikit berubah
        freq1 = CH1_BASE_FREQ + np.random.randint(-CH1_JITTER, CH1_JITTER + 1)
        freq2 = CH2_BASE_FREQ + np.random.randint(-CH2_JITTER, CH2_JITTER + 1)
        
        t = np.linspace(0, NUM_SAMPLES / SAMPLE_RATE, NUM_SAMPLES, endpoint=False)
        
        # Buat data untuk dua channel
        signal1 = (1000 * np.sin(2 * np.pi * freq1 * t)).astype(np.uint16)
        signal2 = (800 * np.sin(2 * np.pi * freq2 * t)).astype(np.uint16)
        
        # Gabungkan (interleave) data seperti hardware asli
        interleaved_data = np.empty((NUM_SAMPLES * 2,), dtype=np.uint16)
        interleaved_data[0::2] = signal1
        interleaved_data[1::2] = signal2

        # Tulis data ke file biner
        with open(FILENAME, "wb") as f:
            f.write(struct.pack(f'<{len(interleaved_data)}H', *interleaved_data))
        
        print(
            f"File updated at {time.strftime('%H:%M:%S')} with freqs "
            f"~{freq1/1000:.1f}kHz (CH1) and ~{freq2/1000:.1f}kHz (CH2)"
        )
        
        # Tunggu sebelum update berikutnya
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nSimulation stopped.")