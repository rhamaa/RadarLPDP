#!/usr/bin/env python3
"""
Radar LPDP Analytics Tool
Interactive panel untuk analisis sample data radar dengan toggle buttons
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import numpy as np
import dearpygui.dearpygui as dpg
from functions.data_processing import load_and_process_data, compute_fft, find_top_extrema
from config import SAMPLE_RATE, FFT_SMOOTHING_ENABLED, FFT_SMOOTHING_WINDOW

# Configuration
SAMPLE_DIR = Path(__file__).parent / "sample"
AVAILABLE_FILES = sorted(list(SAMPLE_DIR.glob("*.bin")))

# Color palette untuk setiap sample
SAMPLE_COLORS = [
    (100, 150, 255),  # Blue
    (255, 150, 100),  # Orange
    (100, 255, 150),  # Green
    (255, 100, 200),  # Pink
    (255, 255, 100),  # Yellow
    (150, 100, 255),  # Purple
    (100, 255, 255),  # Cyan
    (255, 150, 150),  # Light Red
]

# Global state
class AnalyticsState:
    def __init__(self):
        self.active_samples = {}  # {filename: {data, color, visible}}
        self.next_color_index = 0
        self.enable_nulling = True  # Enable data nulling below 10th peak
        self.nulling_threshold_rank = 10  # Null data below this peak rank
    
    def toggle_sample(self, filename):
        """Toggle visibility sample"""
        if filename in self.active_samples:
            # Remove sample
            del self.active_samples[filename]
            return False
        else:
            # Add sample
            self.load_sample(filename)
            return True
    
    def load_sample(self, filename):
        """Load dan process sample file"""
        filepath = SAMPLE_DIR / filename
        
        if not filepath.exists():
            print(f"❌ File not found: {filename}")
            return
        
        print(f"📂 Loading: {filename}")
        
        # Load data
        ch1, ch2, n_samples, sr = load_and_process_data(str(filepath), SAMPLE_RATE)
        
        if ch1 is None:
            print(f"❌ Failed to load {filename}")
            return
        
        # Compute FFT
        freqs_ch1, mag_ch1 = compute_fft(
            ch1, SAMPLE_RATE,
            smooth=FFT_SMOOTHING_ENABLED,
            smooth_window=FFT_SMOOTHING_WINDOW
        )
        freqs_ch2, mag_ch2 = compute_fft(
            ch2, SAMPLE_RATE,
            smooth=FFT_SMOOTHING_ENABLED,
            smooth_window=FFT_SMOOTHING_WINDOW
        )
        
        # Find peaks (get more untuk nulling)
        ch1_peaks, _ = find_top_extrema(freqs_ch1, mag_ch1, n_extrema=20)
        ch2_peaks, _ = find_top_extrema(freqs_ch2, mag_ch2, n_extrema=20)
        
        # Apply data nulling jika enabled
        if self.enable_nulling and len(ch1_peaks) > self.nulling_threshold_rank:
            mag_ch1 = self._apply_nulling(mag_ch1, ch1_peaks, self.nulling_threshold_rank)
        if self.enable_nulling and len(ch2_peaks) > self.nulling_threshold_rank:
            mag_ch2 = self._apply_nulling(mag_ch2, ch2_peaks, self.nulling_threshold_rank)
        
        # Assign color
        color = SAMPLE_COLORS[self.next_color_index % len(SAMPLE_COLORS)]
        self.next_color_index += 1
        
        # Store data
        self.active_samples[filename] = {
            'ch1_data': ch1,
            'ch2_data': ch2,
            'freqs_ch1': freqs_ch1,
            'mag_ch1': mag_ch1,
            'freqs_ch2': freqs_ch2,
            'mag_ch2': mag_ch2,
            'ch1_peaks': ch1_peaks,
            'ch2_peaks': ch2_peaks,
            'color': color,
            'n_samples': n_samples
        }
        
        print(f"✅ Loaded {filename}: {n_samples} samples, {len(ch1_peaks)} CH1 peaks, {len(ch2_peaks)} CH2 peaks")
    
    def _apply_nulling(self, magnitudes, peaks, threshold_rank):
        """Null (set to minimum) data yang bukan termasuk top N peaks"""
        if len(peaks) <= threshold_rank:
            return magnitudes
        
        # Get threshold magnitude dari peak ke-N
        threshold_mag = peaks[threshold_rank - 1]['mag_db']
        
        # Create nulled version
        mag_nulled = magnitudes.copy()
        min_mag = np.min(magnitudes)
        
        # Set semua data di bawah threshold ke minimum
        mag_nulled[mag_nulled < threshold_mag] = min_mag
        
        return mag_nulled

state = AnalyticsState()

# Callbacks
def toggle_button_callback(sender, app_data, user_data):
    """Callback untuk toggle button sample"""
    filename = user_data
    
    # Toggle sample
    is_active = state.toggle_sample(filename)
    
    # Update button appearance
    if is_active:
        dpg.configure_item(sender, label=f"✓ {filename}")
    else:
        dpg.configure_item(sender, label=f"  {filename}")
    
    # Update plots
    update_all_plots()

def update_all_plots():
    """Update semua plot dengan data aktif"""
    # Clear existing series
    clear_plot_series("fft_ch1_yaxis")
    clear_plot_series("fft_ch2_yaxis")
    
    # Clear peak table
    clear_peak_table()
    
    if not state.active_samples:
        return
    
    # Add series untuk setiap active sample
    for filename, data in state.active_samples.items():
        color = data['color']
        
        # Add CH1 series
        ch1_series = dpg.add_line_series(
            data['freqs_ch1'],
            data['mag_ch1'],
            label=f"{filename} - CH1",
            parent="fft_ch1_yaxis",
        )
        dpg.bind_item_theme(ch1_series, create_line_theme(color))
        
        # Add CH2 series
        ch2_series = dpg.add_line_series(
            data['freqs_ch2'],
            data['mag_ch2'],
            label=f"{filename} - CH2",
            parent="fft_ch2_yaxis",
        )
        dpg.bind_item_theme(ch2_series, create_line_theme(color))
    
    # Auto-fit axes
    dpg.fit_axis_data("fft_ch1_xaxis")
    dpg.fit_axis_data("fft_ch1_yaxis")
    dpg.fit_axis_data("fft_ch2_xaxis")
    dpg.fit_axis_data("fft_ch2_yaxis")
    
    # Update peak table
    update_peak_table()

def clear_plot_series(axis_tag):
    """Clear all series dari axis"""
    children = dpg.get_item_children(axis_tag, slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

def clear_peak_table():
    """Clear peak table"""
    for table_tag in ["ch1_peak_table", "ch2_peak_table"]:
        if dpg.does_item_exist(table_tag):
            children = dpg.get_item_children(table_tag, slot=1)
            if children:
                for child in children:
                    dpg.delete_item(child)

def update_peak_table():
    """Update tabel peak dengan data dari semua active samples"""
    for filename, data in state.active_samples.items():
        color = data['color']
        
        # CH1 peaks
        if dpg.does_item_exist("ch1_peak_table"):
            for i, peak in enumerate(data['ch1_peaks'][:5]):  # Top 5
                with dpg.table_row(parent="ch1_peak_table"):
                    dpg.add_text(filename, color=color)
                    dpg.add_text(f"{i+1}")
                    dpg.add_text(f"{peak['index']}")
                    dpg.add_text(f"{peak['freq_khz']:.2f}")
                    dpg.add_text(f"{peak['mag_db']:.2f}")
        
        # CH2 peaks
        if dpg.does_item_exist("ch2_peak_table"):
            for i, peak in enumerate(data['ch2_peaks'][:5]):  # Top 5
                with dpg.table_row(parent="ch2_peak_table"):
                    dpg.add_text(filename, color=color)
                    dpg.add_text(f"{i+1}")
                    dpg.add_text(f"{peak['index']}")
                    dpg.add_text(f"{peak['freq_khz']:.2f}")
                    dpg.add_text(f"{peak['mag_db']:.2f}")

def create_line_theme(color):
    """Create theme untuk line series dengan warna tertentu"""
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
    return theme_id

def toggle_nulling_callback(sender, app_data):
    """Toggle data nulling on/off"""
    state.enable_nulling = app_data
    
    # Reload all active samples
    active_files = list(state.active_samples.keys())
    state.active_samples.clear()
    
    for filename in active_files:
        state.load_sample(filename)
    
    update_all_plots()
    print(f"🔧 Data nulling: {'ON' if app_data else 'OFF'}")

def nulling_threshold_callback(sender, app_data):
    """Update nulling threshold rank"""
    state.nulling_threshold_rank = int(app_data)
    
    # Reload all active samples
    active_files = list(state.active_samples.keys())
    state.active_samples.clear()
    
    for filename in active_files:
        state.load_sample(filename)
    
    update_all_plots()
    print(f"🔧 Nulling threshold: Top {app_data} peaks")

def clear_all_callback():
    """Clear semua active samples"""
    state.active_samples.clear()
    state.next_color_index = 0
    
    # Reset all buttons
    for f in AVAILABLE_FILES:
        button_tag = f"btn_{f.name}"
        if dpg.does_item_exist(button_tag):
            dpg.configure_item(button_tag, label=f"  {f.name}")
    
    update_all_plots()

# Main UI
def create_analytics_panel():
    """Buat panel analytics dengan DearPyGUI"""
    
    dpg.create_context()
    
    # Setup theme
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (15, 15, 15))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (30, 30, 30))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 50, 70))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 70, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (80, 120, 180))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 5, 5)
    
    dpg.bind_theme(global_theme)
    
    # Main window
    with dpg.window(label="Radar LPDP Analytics", tag="main_window", width=1600, height=950):
        
        dpg.add_text("📊 Radar Sample Comparison Tool", color=(100, 200, 255))
        dpg.add_text("Click buttons to toggle samples (multiple selection allowed)", color=(150, 150, 150))
        dpg.add_separator()
        
        # Top bar - Sample toggle buttons
        with dpg.group(horizontal=True):
            dpg.add_text("📁 Samples:", color=(200, 200, 100))
            
            for f in AVAILABLE_FILES:
                dpg.add_button(
                    label=f"  {f.name}",
                    callback=toggle_button_callback,
                    user_data=f.name,
                    tag=f"btn_{f.name}",
                    width=120
                )
            
            dpg.add_button(
                label="🗑️ Clear All",
                callback=clear_all_callback,
                width=100
            )
        
        dpg.add_separator()
        
        # Layout: 2 columns
        with dpg.group(horizontal=True):
            
            # Left column: FFT Plots
            with dpg.child_window(width=1050, height=850):
                dpg.add_text("FFT Spectrum Comparison", color=(100, 200, 255))
                dpg.add_text("Multiple samples can be overlayed for comparison", color=(150, 150, 150))
                
                dpg.add_spacer(height=5)
                
                # CH1 Plot
                dpg.add_text("Channel 1 (CH1)", color=(255, 150, 100))
                with dpg.plot(label="CH1 FFT Comparison", height=380, width=-1, tag="ch1_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="fft_ch1_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="fft_ch1_yaxis")

                
                dpg.add_spacer(height=10)
                
                # CH2 Plot
                dpg.add_text("Channel 2 (CH2)", color=(255, 200, 100))
                with dpg.plot(label="CH2 FFT Comparison", height=380, width=-1, tag="ch2_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="fft_ch2_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="fft_ch2_yaxis")
            
            # Right column: Peak Tables & Controls
            with dpg.child_window(width=500, height=850):
                dpg.add_text("Controls & Peak Analysis", color=(100, 255, 150))
                
                dpg.add_spacer(height=5)
                
                # Nulling controls
                with dpg.collapsing_header(label="🔧 Data Nulling (Grass Removal)", default_open=True):
                    dpg.add_text("Remove noise below top N peaks:", color=(200, 200, 200))
                    dpg.add_checkbox(
                        label="Enable Nulling",
                        default_value=True,
                        callback=toggle_nulling_callback
                    )
                    dpg.add_slider_int(
                        label="Keep Top N Peaks",
                        default_value=10,
                        min_value=5,
                        max_value=20,
                        callback=nulling_threshold_callback,
                        width=200
                    )
                    dpg.add_text("💡 Lower value = more aggressive noise removal", color=(150, 150, 150))
                
                dpg.add_separator()
                dpg.add_spacer(height=5)
                
                # CH1 Peaks
                dpg.add_text("CH1 Top Peaks", color=(255, 150, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="ch1_peak_table",
                    height=380,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Sample", width_fixed=True, init_width_or_weight=100)
                    dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=30)
                    dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=60)
                    dpg.add_table_column(label="Freq (kHz)", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Mag (dB)", width_fixed=True, init_width_or_weight=80)
                
                dpg.add_spacer(height=20)
                
                # CH2 Peaks
                dpg.add_text("CH2 Top Peaks", color=(255, 200, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="ch2_peak_table",
                    height=380,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Sample", width_fixed=True, init_width_or_weight=100)
                    dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=30)
                    dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=60)
                    dpg.add_table_column(label="Freq (kHz)", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Mag (dB)", width_fixed=True, init_width_or_weight=80)
        
        dpg.add_separator()
        dpg.add_text("💡 Tip: Click multiple sample buttons to overlay and compare FFT spectra", 
                     color=(150, 150, 150))
    
    # Setup viewport
    dpg.create_viewport(title="Radar LPDP Analytics - Sample Comparison", width=1620, height=970)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    
    print("✅ Analytics panel created!")
    print(f"📁 Found {len(AVAILABLE_FILES)} sample files")
    print("🚀 Click sample buttons to load and compare data")
    
    # Render loop
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()
    
    dpg.destroy_context()
    print("👋 Analytics panel closed")

if __name__ == "__main__":
    print("="*60)
    print("🎯 Radar LPDP Analytics Tool")
    print("="*60)
    print(f"📂 Sample directory: {SAMPLE_DIR}")
    print(f"📊 Available samples: {len(AVAILABLE_FILES)}")
    for f in AVAILABLE_FILES:
        print(f"   - {f.name}")
    print("="*60)
    
    create_analytics_panel()
