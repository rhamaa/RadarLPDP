# app/setup.py

import dearpygui.dearpygui as dpg
import threading
import queue
import os

# Impor dari file lokal
from config import APP_SPACING, APP_PADDING, THEME_COLORS, PROJECT_ROOT
from functions.data_processing import fft_data_worker, sinewave_data_worker, angle_worker
from app.callbacks import resize_callback

def _preload_textures():
    """Load commonly used textures into the global texture registry."""
    if not dpg.does_item_exist("texture_registry"):
        dpg.add_texture_registry(tag="texture_registry")

    assets_dir = os.path.join(PROJECT_ROOT, "Assets")
    textures = [
        ("logo_lpdp", os.path.join(assets_dir, "Logo_LPDP.png")),
        ("logo_dkst", os.path.join(assets_dir, "DKST_ITB.png")),
        ("logo_kirei", os.path.join(assets_dir, "KIREI.png")),
    ]

    for tag, path in textures:
        if dpg.does_item_exist(tag):
            continue
        if not os.path.exists(path):
            print(f"[textures] file tidak ditemukan: {path}")
            continue
        try:
            width, height, channels, data = dpg.load_image(path)
            dpg.add_static_texture(width, height, data, tag=tag, parent="texture_registry")
        except Exception as e:
            print(f"[textures] gagal memuat {path}: {e}")

def initialize_queues_and_events():
    """Membuat semua queues dan events yang dibutuhkan untuk threading."""
    queues = {
        'ppi': queue.Queue(),
        'fft': queue.Queue(),
        'sinewave': queue.Queue()
    }
    stop_event = threading.Event()
    return queues, stop_event

def start_worker_threads(queues, stop_event):
    # Membuat dan memulai thread untuk setiap worker
    # fft_data_worker sekarang juga menangani data PPI
    fft_thread = threading.Thread(target=fft_data_worker, args=(queues['fft'], queues['ppi'], stop_event), daemon=True)
    sinewave_thread = threading.Thread(target=sinewave_data_worker, args=(queues['sinewave'], stop_event), daemon=True)
    angle_thread = threading.Thread(target=angle_worker, args=(queues['ppi'], stop_event), daemon=True)

    threads = {
        'fft': fft_thread,
        'sinewave': sinewave_thread,
        'angle': angle_thread
    }

    for thread in threads.values():
        thread.start()
    return threads

def setup_dpg(title='Real-time Radar UI & Spectrum Analyzer', width=1280, height=720):
    """Menginisialisasi Dear PyGui, viewport, tema, dan handler."""
    dpg.create_context()

    # Pastikan registri tekstur global tersedia di root (bukan di dalam window)
    if not dpg.does_item_exist("texture_registry"):
        dpg.add_texture_registry(tag="texture_registry")

    # Preload logo textures sebelum membuat window/layout apapun
    _preload_textures()

    # Definisikan tema global
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, APP_PADDING, APP_PADDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, APP_SPACING, APP_SPACING)
            dpg.add_theme_color(dpg.mvPlotCol_PlotBg, THEME_COLORS["background"])
    dpg.bind_theme(global_theme)

    # Atur handler untuk keluar dengan tombol Esc
    with dpg.handler_registry():
        dpg.add_key_press_handler(key=dpg.mvKey_Escape, callback=dpg.stop_dearpygui)

    # Konfigurasi viewport
    dpg.create_viewport(title=title, width=width, height=height)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_viewport_resize_callback(resize_callback)
