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
            dpg.set_value("fft_ch1_series", [result["freqs_ch1"].tolist(), result["mag_ch1"].tolist()])
            dpg.set_value("fft_ch2_series", [result["freqs_ch2"].tolist(), result["mag_ch2"].tolist()])
            
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
    """Menyesuaikan ukuran layout saat window di-resize."""
    if not dpg.is_dearpygui_running():
        return
    
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    
    left_width = int(viewport_width * 0.7)
    dpg.set_item_width("left_column", left_width)
    dpg.set_item_width("right_column", -1)
    
    available_height = viewport_height - (APP_PADDING * 2)
    left_col_height = available_height - APP_SPACING
    right_col_height = available_height - (APP_SPACING * 2)
    
    dpg.set_item_height("ppi_window", int(left_col_height * 0.6))
    dpg.set_item_height("fft_window", int(left_col_height * 0.4))
    dpg.set_item_height("file_explorer_window", int(right_col_height * 0.35))
    dpg.set_item_height("sinewave_window", int(right_col_height * 0.35))
    dpg.set_item_height("controller_window", int(right_col_height * 0.30))

def cleanup_and_exit(stop_event, threads):
    """Memberhentikan thread worker dengan aman dan menutup Dear PyGui."""
    print("Stopping worker threads...")
    stop_event.set()
    time.sleep(0.5)
    for t in threads:
        t.join()
    print("All threads stopped. Destroying context.")
    dpg.destroy_context()
