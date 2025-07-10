# widgets/PPI.py

import dearpygui.dearpygui as dpg
import numpy as np
import math

# Impor dari file lokal
from functions.data_processing import polar_to_cartesian
from config import THEME_COLORS

# --- Helper Khusus UI --- #

def generate_arc_points(center, radius, start_deg, end_deg, segments=100):
    """Menghasilkan titik-titik untuk menggambar busur."""
    points = []
    start_rad, end_rad = math.radians(start_deg), math.radians(end_deg)
    for i in range(segments + 1):
        angle = start_rad + (end_rad - start_rad) * i / segments
        points.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    return points

# --- Fungsi Pembuat Widget UI --- #

def create_ppi_widget(parent, width, height):
    """Membuat widget PPI dengan skala, lingkaran jarak, dan series untuk data."""
    with dpg.child_window(parent=parent, width=width, height=height, no_scrollbar=True):
        dpg.add_text("Plan Position Indicator (PPI) - Jarak (km)")
        
        axis_limit = 50
        
        with dpg.plot(label="PPI Display", width=-1, height=-1, equal_aspects=True):
            dpg.add_plot_legend()
            
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="", no_tick_labels=True, lock_min=True, lock_max=True)
            dpg.set_axis_limits(x_axis, -axis_limit, axis_limit)
            
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="", no_tick_labels=True, lock_min=True, lock_max=True)
            dpg.set_axis_limits(y_axis, 0, axis_limit) # Batas Y dari 0 hingga 50

            # Menggambar busur jarak 180 derajat (range rings)
            for r in range(10, axis_limit + 1, 10):
                theta = np.linspace(0, np.pi, 100) # 0 hingga pi untuk 180 derajat
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                dpg.add_line_series(list(x), list(y), parent=y_axis, label=f"{r} km")

            # Garis untuk sapuan radar (akan diupdate)
            dpg.add_line_series([0], [0], label="Sweep", tag="ppi_sweep_line", parent=y_axis)
            
            # Titik untuk target (akan diupdate)
            dpg.add_scatter_series([], [], label="Targets", tag="ppi_targets", parent=y_axis)

def update_ppi_widget(angle: float, targets: list):
    """
    Memperbarui garis sapuan PPI dan titik-titik target.

    Args:
        angle (float): Sudut sapuan saat ini dalam derajat (0-180).
        targets (list): Daftar tuple, di mana setiap tuple adalah (sudut, jarak).
    """
    # Perbarui garis sapuan
    max_range = 50  # Jangkauan maksimum plot adalah 50 km
    rad_angle = np.radians(angle)
    sweep_x = max_range * np.cos(rad_angle)
    sweep_y = max_range * np.sin(rad_angle)
    dpg.set_value("ppi_sweep_line", ([0, sweep_x], [0, sweep_y]))

    # Perbarui target
    if targets:
        target_x = [dist * np.cos(np.radians(ang)) for ang, dist in targets]
        target_y = [dist * np.sin(np.radians(ang)) for ang, dist in targets]
    else:
        target_x, target_y = [], []
    
    # Pastikan data C-contiguous untuk Dear PyGui
    dpg.set_value("ppi_targets", (np.ascontiguousarray(target_x, dtype=np.float64), np.ascontiguousarray(target_y, dtype=np.float64)))

