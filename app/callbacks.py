# app/callbacks.py

import dearpygui.dearpygui as dpg
import queue
import time
import numpy as np

# Impor dari file lokal
from config import APP_SPACING, APP_PADDING, THEME_COLORS
from widgets.PPI import update_sweep_line, add_target_to_plot
from app.external_process import stop_worker

# Variabel global untuk state UI
last_known_angle = 0
target_history = []

def update_ui_from_queues(queues):
    """Memeriksa semua queue dan mengupdate UI jika ada data baru."""
    global last_known_angle, target_history

    # --- Antrian PPI (sekarang menangani dua jenis pesan) ---
    try:
        ppi_data = queues['ppi'].get_nowait()
        
        if ppi_data['type'] == 'sweep':
            # Pesan dari angle_worker: hanya perbarui sudut dan garis sapuan
            last_known_angle = ppi_data['angle']
            update_sweep_line(last_known_angle)

        elif ppi_data['type'] == 'target':
            # Pesan dari fft_data_worker: tambahkan target baru pada sudut terakhir yang diketahui
            distance = ppi_data['distance']
            new_target = (last_known_angle, distance)
            target_history.append(new_target)
            if len(target_history) > 50: # Batasi riwayat
                target_history.pop(0)
            
            add_target_to_plot(target_history)
    except queue.Empty:
        pass

    # --- Update FFT & Metrics --- #
    try:
        fft_data = queues['fft'].get_nowait()
        status = fft_data.get("status")
        
        if status == "processing":
            dpg.set_value("fft_status_text", "Processing...")
        elif status in ["error", "waiting"]:
            dpg.set_value("fft_status_text", fft_data.get("message"))
        elif status == "done":
            dpg.set_value("fft_status_text", f"Updated: {time.strftime('%H:%M:%S')}")
            
            # Update plot FFT
            dpg.set_value('fft_ch1_series', [fft_data["freqs_ch1"], fft_data["mag_ch1"]])
            dpg.set_value('fft_ch2_series', [fft_data["freqs_ch2"], fft_data["mag_ch2"]])
            dpg.set_axis_limits_auto("fft_yaxis")

            # Update widget metrik
            metrics = fft_data["metrics"]
            dpg.set_value("ch1_peak_freq", f"{metrics['ch1']['peak_freq']:.2f}")
            dpg.set_value("ch1_peak_mag", f"{metrics['ch1']['peak_mag']:.2f}")
            dpg.set_value("ch2_peak_freq", f"{metrics['ch2']['peak_freq']:.2f}")
            dpg.set_value("ch2_peak_mag", f"{metrics['ch2']['peak_mag']:.2f}")

            # Update tabel Peaks & Valleys
            def update_extrema_table(prefix, peaks, valleys, max_rows=5):
                # Gabungkan: puncak dulu lalu lembah, batasi ke max_rows
                combined = [("peak", p) for p in peaks] + [("valley", v) for v in valleys]
                combined = combined[:max_rows]
                # Isi baris yang tersedia
                for i in range(max_rows):
                    if i < len(combined):
                        t, item = combined[i]
                        dpg.set_value(f"{prefix}_ext_{i}_index", str(item.get("index", "-")))
                        dpg.set_value(f"{prefix}_ext_{i}_freq", f"{item.get('freq_khz', 0.0):.2f}")
                        dpg.set_value(f"{prefix}_ext_{i}_mag", f"{item.get('mag_db', 0.0):.2f}")
                        dpg.set_value(f"{prefix}_ext_{i}_type", "Peak" if t == "peak" else "Valley")
                    else:
                        dpg.set_value(f"{prefix}_ext_{i}_index", "-")
                        dpg.set_value(f"{prefix}_ext_{i}_freq", "-")
                        dpg.set_value(f"{prefix}_ext_{i}_mag", "-")
                        dpg.set_value(f"{prefix}_ext_{i}_type", "-")

            ch1 = metrics.get('ch1', {})
            ch2 = metrics.get('ch2', {})
            update_extrema_table('ch1', ch1.get('peaks', []), ch1.get('valleys', []), max_rows=5)
            update_extrema_table('ch2', ch2.get('peaks', []), ch2.get('valleys', []), max_rows=5)

    except queue.Empty:
        pass

    # --- Update Sinewave --- #
    try:
        sinewave_data = queues['sinewave'].get_nowait()
        if sinewave_data.get("status") == "done":
            time_axis = np.ascontiguousarray(sinewave_data["time_axis"])
            ch1_data = np.ascontiguousarray(sinewave_data["ch1_data"])
            ch2_data = np.ascontiguousarray(sinewave_data["ch2_data"])
            dpg.set_value("sinewave_ch1_series", [time_axis, ch1_data])
            dpg.set_value("sinewave_ch2_series", [time_axis, ch2_data])
            dpg.set_axis_limits_auto("sinewave_xaxis")
            dpg.set_axis_limits_auto("sinewave_yaxis")
    except queue.Empty:
        pass

def resize_callback():
    """Menyesuaikan ukuran layout secara dinamis saat window di-resize."""
    if not dpg.is_dearpygui_running():
        return

    viewport_width = dpg.get_viewport_client_width()
    viewport_height = dpg.get_viewport_client_height()

    # Tentukan padding dan spasi untuk kalkulasi
    padding = APP_PADDING * 2
    spacing = APP_SPACING

    # Kalkulasi lebar kolom
    left_col_width = int(viewport_width * 0.7) - spacing
    right_col_width = viewport_width - left_col_width - (spacing * 2)

    dpg.set_item_width("left_column", left_col_width)
    dpg.set_item_width("right_column", right_col_width)

    # Kalkulasi tinggi panel di kolom kiri
    available_height_left = viewport_height - padding
    ppi_height = int(available_height_left * 0.65) - spacing
    fft_height = available_height_left - ppi_height - spacing

    dpg.set_item_height("ppi_window", ppi_height)
    dpg.set_item_height("fft_window", fft_height)

    # Kalkulasi tinggi panel di kolom kanan
    available_height_right = viewport_height - padding
    panel_height = (available_height_right - (spacing * 3)) // 4

    dpg.set_item_height("sinewave_window", panel_height)
    dpg.set_item_height("metrics_window", panel_height)
    dpg.set_item_height("file_explorer_window", panel_height)
    dpg.set_item_height("controller_window", panel_height)

def cleanup_and_exit(stop_event, threads):
    """Memberhentikan thread worker dengan aman dan menutup Dear PyGui."""
    print("Stopping worker threads...")
    stop_event.set()
    time.sleep(0.5)
    for t in threads.values():
        t.join()
    print("All threads stopped. Destroying context.")
    # Pastikan proses eksternal juga dihentikan
    try:
        stop_worker()
    except Exception as e:
        print(f"[external_worker] stop error: {e}")
    dpg.destroy_context()
