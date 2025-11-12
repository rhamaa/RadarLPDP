# compare_fft_vs_rfft.py
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import rfft, rfftfreq

from functions.data_processing import load_and_process_data  # @functions/data_processing.py#68-114
from config import SAMPLE_RATE  # @config.py#45-48

# Ganti path ini agar menunjuk ke file bin yang ingin diuji
FILE_PATH = Path(
    "analytics/sample/LNA HIDUP/GROUP1/GERBANG 10 M/G1.bin"
).resolve()

def main():
    ch1, ch2, n_samples, _ = load_and_process_data(str(FILE_PATH), SAMPLE_RATE)
    if ch1 is None or n_samples == 0:
        raise RuntimeError("File tidak valid atau kosong")

    # pilih kanal yang mau dianalisis
    signal = np.asarray(ch1, dtype=np.float64)

    # FFT penuh (frekuensi positif + negatif)
    full_fft = np.fft.fft(signal)
    full_freqs = np.fft.fftfreq(n_samples, d=1 / SAMPLE_RATE)

    # gunakan hanya frekuensi positif untuk plot agar sebanding
    pos_mask = full_freqs >= 0
    full_freqs_pos = full_freqs[pos_mask] / 1e6  # ke MHz
    full_mag_pos = np.abs(full_fft[pos_mask])

    # RFFT (hanya frekuensi positif)
    real_fft = rfft(signal)
    real_freqs = rfftfreq(n_samples, d=1 / SAMPLE_RATE) / 1e6
    real_mag = np.abs(real_fft)

    # Plot side-by-side (atas/bawah)
    fig, (ax_full, ax_real) = plt.subplots(
        2, 1, figsize=(10, 8), sharex=True, constrained_layout=True
    )

    ax_full.plot(full_freqs_pos, full_mag_pos)
    ax_full.set_title("Full FFT (magnitudo vs frekuensi)")
    ax_full.set_ylabel("Magnitude")
    ax_full.grid(True, alpha=0.3)

    ax_real.plot(real_freqs, real_mag, color="orange")
    ax_real.set_title("Real FFT (rFFT)")
    ax_real.set_xlabel("Frekuensi (MHz)")
    ax_real.set_ylabel("Magnitude")
    ax_real.grid(True, alpha=0.3)

    plt.show()

if __name__ == "__main__":
    main()