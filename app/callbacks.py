# app/callbacks.py

import dearpygui.dearpygui as dpg
import time
import queue

# Impor dari file lokal
from config import APP_SPACING, APP_PADDING, THEME_COLORS
from functions.data_processing import polar_to_cartesian

def update_ui_from_queues(queues):
    """Memeriksa semua queue dan mengupdate UI jika ada data baru."""

    # Update PPI
    try:
        ppi_data = queues['ppi'].get_nowait()
        dpg.delete_item("ppi_dynamic_layer", children_only=True)
        accent_color = THEME_COLORS["accent"]
        
        angles_history = ppi_data["angles"]
        history_len = len(angles_history)
        for i, angle in enumerate(angles_history):
            alpha = int(255 * ((i + 1) / history_len))
            faded_color = (*accent_color[:3], alpha)
            p0 = (0, 0)
            p1 = polar_to_cartesian(0, 0, angle - 0.5, 100)
            p2 = polar_to_cartesian(0, 0, angle + 0.5, 100)
            dpg.draw_polygon(points=[p0, p1, p2], color=faded_color, fill=faded_color, parent="ppi_dynamic_layer")
        
        for angle, radius in ppi_data["targets"]:
            target_pos = polar_to_cartesian(0, 0, angle, radius)
            dpg.draw_circle(center=target_pos, radius=2, color=THEME_COLORS["target"], fill=THEME_COLORS["target"], parent="ppi_dynamic_layer")

    except queue.Empty:
        pass

    # Update FFT
    try:
        result = queues['fft'].get_nowait()
        status = result.get("status")
        
        if status == "processing":
            dpg.set_value("fft_status_text", "File changed, processing...")
        elif status in ["error", "waiting"]:
            dpg.set_value("fft_status_text", result.get("message"))
        elif status == "done":
            update_time = time.strftime('%H:%M:%S')
            dpg.set_value("fft_status_text", f"Plot updated at: {update_time}")
            data = result
            if "freqs_ch1" in data and "mag_ch1" in data:
                dpg.set_value('fft_ch1_series', [data["freqs_ch1"], data["mag_ch1"]])
            if "freqs_ch2" in data and "mag_ch2" in data:
                dpg.set_value('fft_ch2_series', [data["freqs_ch2"], data["mag_ch2"]])

            # Perbarui widget metrik jika data ada
            if "metrics" in data:
                metrics = data["metrics"]
                # Channel 1
                dpg.set_value("ch1_peak_freq", f"{metrics['ch1']['peak_freq']:.2f}")
                dpg.set_value("ch1_peak_mag", f"{metrics['ch1']['peak_mag']:.2f}")
                # Channel 2
                dpg.set_value("ch2_peak_freq", f"{metrics['ch2']['peak_freq']:.2f}")
                dpg.set_value("ch2_peak_mag", f"{metrics['ch2']['peak_mag']:.2f}")

            sr, n_samples = result["sample_rate"], result["n_samples"]
            freq_res = sr / n_samples if n_samples > 0 else 0
            plot_label = f'Live FFT Spectrum\nSR: {sr/1e6:.2f}MHz, N: {n_samples}, Res: {freq_res:.1f}Hz'
            dpg.configure_item("fft_plot", label=plot_label)
            dpg.set_axis_limits_auto("fft_yaxis")

    except queue.Empty:
        pass

    # Update Sinewave
    try:
        result = queues['sinewave'].get_nowait()
        if result.get("status") == "done":
            dpg.set_value("sinewave_status_text", f"Waveform updated at: {time.strftime('%H:%M:%S')}")
            dpg.set_value("sinewave_ch1_series", [result["time_axis"].tolist(), result["ch1_data"].tolist()])
            dpg.set_value("sinewave_ch2_series", [result["time_axis"].tolist(), result["ch2_data"].tolist()])
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
    for t in threads:
        t.join()
    print("All threads stopped. Destroying context.")
    dpg.destroy_context()
