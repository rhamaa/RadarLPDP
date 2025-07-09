# main.py
# File ini hanya bertanggung jawab untuk mendefinisikan layout UI dan menjalankan aplikasi.

import dearpygui.dearpygui as dpg

# Impor fungsi setup dan callback dari modul terpisah
from app.setup import setup_dpg, initialize_queues_and_events, start_worker_threads
from app.callbacks import update_ui_from_queues, cleanup_and_exit, resize_callback

# Impor semua widget UI
from widgets.PPI import create_ppi_widget
from widgets.FFT import create_fft_widget
from widgets.Sinewave import create_sinewave_widget
from widgets.file import create_file_explorer_widget
from widgets.controller import create_controller_widget

# --- Definisi Layout UI --- #
def create_main_layout():
    """Mendefinisikan dan membuat semua widget di dalam window utama."""
    with dpg.window(tag="Primary Window"):
        with dpg.group(horizontal=True):
            # Kolom kiri (70% lebar)
            with dpg.group(tag="left_column"):
                with dpg.child_window(label="PPI Desktop", tag="ppi_window", no_scrollbar=True):
                    create_ppi_widget()
                with dpg.child_window(label="FFT Desktop", tag="fft_window"):
                    create_fft_widget()
            # Kolom kanan (sisa lebar)
            with dpg.group(tag="right_column"):
                with dpg.child_window(label="File Explorer", tag="file_explorer_window"):
                    create_file_explorer_widget()
                with dpg.child_window(label="Sinewave", tag="sinewave_window"):
                    create_sinewave_widget()
                with dpg.child_window(label="Controller", tag="controller_window"):
                    create_controller_widget()

# --- Titik Masuk Aplikasi --- #
if __name__ == "__main__":
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