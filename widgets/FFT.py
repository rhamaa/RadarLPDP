# widgets/FFT.py

import dearpygui.dearpygui as dpg
import os

# Impor konfigurasi terpusat
from config import FILENAME

# --- Fungsi Pembuat Widget UI --- #

def create_fft_widget(parent, width, height):
    """Membuat widget UI untuk menampilkan FFT Spectrum."""
    with dpg.group(parent=parent):
        # Menggunakan os.path.basename untuk menampilkan nama file saja, bukan path lengkap
        dpg.add_text(f"Monitoring '{os.path.basename(FILENAME)}'...", tag="fft_status_text")
        
        with dpg.plot(label="Live FFT Spectrum", height=height, width=width, tag="fft_plot"):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (KHz)", tag="fft_xaxis", log_scale=True)
            dpg.set_axis_limits("fft_xaxis", 10, 10000) # Batas dalam KHz (10 KHz hingga 10 MHz)
            dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="fft_yaxis")
            dpg.add_line_series([], [], label="CH1 (odd)", parent="fft_yaxis", tag="fft_ch1_series")
            dpg.add_line_series([], [], label="CH2 (even)", parent="fft_yaxis", tag="fft_ch2_series")