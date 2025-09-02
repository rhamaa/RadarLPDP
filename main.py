# main.py
# File ini hanya bertanggung jawab untuk mendefinisikan layout UI dan menjalankan aplikasi.

import dearpygui.dearpygui as dpg

# Impor fungsi setup dan callback dari modul terpisah
from app.setup import setup_dpg, initialize_queues_and_events, start_worker_threads
from app.callbacks import update_ui_from_queues, cleanup_and_exit, resize_callback
import atexit
from config import EXTERNAL_WORKER
from app.external_process import start_worker, stop_worker

# Impor semua widget UI
from widgets.PPI import create_ppi_widget
from widgets.FFT import create_fft_widget
from widgets.Sinewave import create_sinewave_widget
from widgets.file import create_file_explorer_widget
from widgets.controller import create_controller_widget
from widgets.metrics import create_metrics_widget

# --- Definisi Layout UI --- #
def create_main_layout():
    """Mendefinisikan dan membuat semua widget di dalam window utama."""
    with dpg.window(tag="Primary Window"):
        with dpg.group(horizontal=True):
            # Kolom kiri
            with dpg.group(tag="left_column"):
                with dpg.child_window(label="PPI Desktop", tag="ppi_window", no_scrollbar=True) as ppi_win:
                    create_ppi_widget(parent=ppi_win, width=-1, height=-1)
                with dpg.child_window(label="FFT Desktop", tag="fft_window", no_scrollbar=True) as fft_win:
                    create_fft_widget(parent=fft_win, width=-1, height=-1)
            
            # Kolom kanan
            with dpg.group(tag="right_column"):
                with dpg.child_window(label="Sinewave", tag="sinewave_window", no_scrollbar=True) as sinewave_win:
                    create_sinewave_widget(parent=sinewave_win, width=-1, height=-1)
                with dpg.child_window(label="Frequency Metrics", tag="metrics_window", no_scrollbar=True) as metrics_win:
                    create_metrics_widget(parent=metrics_win, width=-1, height=-1)
                with dpg.child_window(label="File Explorer", tag="file_explorer_window", no_scrollbar=True) as file_explorer_win:
                    create_file_explorer_widget(parent=file_explorer_win, width=-1, height=-1)
                with dpg.child_window(label="Controller", tag="controller_window", no_scrollbar=True) as controller_win:
                    create_controller_widget(parent=controller_win, width=-1, height=-1)

# --- Titik Masuk Aplikasi --- #
if __name__ == "__main__":
    # 0. Jalankan background worker eksternal (sebelum app utama)
    try:
        start_worker(EXTERNAL_WORKER)
    except Exception as e:
        print(f"[external_worker] gagal start: {e}")
    atexit.register(stop_worker)

    # 1. Inisialisasi Dear PyGui (viewport, tema, handler)
    setup_dpg()

    # 2. Buat layout UI utama
    create_main_layout()
    dpg.set_primary_window("Primary Window", True)

    # Panggil fullscreen dan resize setelah layout dibuat untuk menghindari error
    dpg.toggle_viewport_fullscreen()
    resize_callback()

    # 3. Siapkan queues dan threads untuk background processing
    queues, stop_event = initialize_queues_and_events()
    threads = start_worker_threads(queues, stop_event)

    # 4. Jalankan main loop
    while dpg.is_dearpygui_running():
        update_ui_from_queues(queues)  # Cek data baru dari worker
        dpg.render_dearpygui_frame()   # Render frame UI

    # 5. Cleanup setelah aplikasi ditutup
    cleanup_and_exit(stop_event, threads)