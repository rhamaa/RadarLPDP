#!/usr/bin/env python3
"""
Radar LPDP Group Comparison Analytics
Analisis persamaan dalam group dan perbedaan antar group
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import dearpygui.dearpygui as dpg
from scipy import stats

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from functions.data_processing import load_and_process_data, compute_fft, find_top_extrema
from config import SAMPLE_RATE, FFT_SMOOTHING_ENABLED, FFT_SMOOTHING_WINDOW

# Configuration
SAMPLE_DIR = Path(__file__).parent / "sample"

# Color palette untuk setiap group
GROUP_COLORS = {
    "5M-Ruangan": (100, 150, 255),   # Blue
    "Langit": (255, 150, 100),       # Orange
}

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

class GroupAnalyzer:
    """Analyzer untuk membandingkan group sample data"""
    
    def __init__(self):
        self.groups = {}  # {group_name: {filename: {data, stats}}}
        self.group_stats = {}  # {group_name: {ch1_stats, ch2_stats}}
        self.selected_groups = set()
        self.enable_nulling = True
        self.nulling_threshold_rank = 10
    
    def discover_groups(self):
        """Discover semua group dari direktori sample"""
        groups = {}
        
        for group_dir in SAMPLE_DIR.iterdir():
            if group_dir.is_dir() and not group_dir.name.startswith('.'):
                bin_files = sorted(list(group_dir.glob("*.bin")))
                if bin_files:
                    groups[group_dir.name] = bin_files
                    print(f"📂 Found group: {group_dir.name} ({len(bin_files)} files)")
        
        return groups
    
    def load_group(self, group_name: str):
        """Load semua sample dalam group"""
        group_dir = SAMPLE_DIR / group_name
        
        if not group_dir.exists():
            print(f"❌ Group not found: {group_name}")
            return False
        
        bin_files = sorted(list(group_dir.glob("*.bin")))
        if not bin_files:
            print(f"❌ No .bin files in {group_name}")
            return False
        
        print(f"📂 Loading group: {group_name}")
        self.groups[group_name] = {}
        
        for filepath in bin_files:
            filename = filepath.name
            
            try:
                # Load data
                ch1, ch2, n_samples, sr = load_and_process_data(str(filepath), SAMPLE_RATE)
                
                if ch1 is None:
                    print(f"  ⚠️  Failed to load {filename}")
                    continue
                
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
                
                # Find peaks
                ch1_peaks, _ = find_top_extrema(freqs_ch1, mag_ch1, n_extrema=20)
                ch2_peaks, _ = find_top_extrema(freqs_ch2, mag_ch2, n_extrema=20)
                
                # Apply nulling if enabled
                if self.enable_nulling and len(ch1_peaks) > self.nulling_threshold_rank:
                    mag_ch1 = self._apply_nulling(mag_ch1, ch1_peaks, self.nulling_threshold_rank)
                if self.enable_nulling and len(ch2_peaks) > self.nulling_threshold_rank:
                    mag_ch2 = self._apply_nulling(mag_ch2, ch2_peaks, self.nulling_threshold_rank)
                
                # Store data
                self.groups[group_name][filename] = {
                    'ch1_data': ch1,
                    'ch2_data': ch2,
                    'freqs_ch1': freqs_ch1,
                    'mag_ch1': mag_ch1,
                    'freqs_ch2': freqs_ch2,
                    'mag_ch2': mag_ch2,
                    'ch1_peaks': ch1_peaks,
                    'ch2_peaks': ch2_peaks,
                    'n_samples': n_samples
                }
                
                print(f"  ✅ {filename}: {n_samples} samples, {len(ch1_peaks)} CH1 peaks, {len(ch2_peaks)} CH2 peaks")
            
            except Exception as e:
                print(f"  ❌ Error loading {filename}: {e}")
        
        # Compute group statistics
        self._compute_group_stats(group_name)
        
        return True
    
    def _apply_nulling(self, magnitudes, peaks, threshold_rank):
        """Null data yang bukan termasuk top N peaks"""
        if len(peaks) <= threshold_rank:
            return magnitudes
        
        threshold_mag = peaks[threshold_rank - 1]['mag_db']
        mag_nulled = magnitudes.copy()
        min_mag = np.min(magnitudes)
        mag_nulled[mag_nulled < threshold_mag] = min_mag
        
        return mag_nulled
    
    def _compute_group_stats(self, group_name: str):
        """Compute statistik untuk group"""
        if group_name not in self.groups:
            return
        
        group_data = self.groups[group_name]
        
        if not group_data:
            return
        
        # Collect all magnitudes
        all_ch1_mags = []
        all_ch2_mags = []
        all_ch1_peaks_freqs = []
        all_ch2_peaks_freqs = []
        
        for filename, data in group_data.items():
            all_ch1_mags.extend(data['mag_ch1'])
            all_ch2_mags.extend(data['mag_ch2'])
            
            for peak in data['ch1_peaks'][:5]:
                all_ch1_peaks_freqs.append(peak['freq_khz'])
            for peak in data['ch2_peaks'][:5]:
                all_ch2_peaks_freqs.append(peak['freq_khz'])
        
        # Compute statistics
        self.group_stats[group_name] = {
            'ch1': {
                'mean_mag': np.mean(all_ch1_mags),
                'std_mag': np.std(all_ch1_mags),
                'min_mag': np.min(all_ch1_mags),
                'max_mag': np.max(all_ch1_mags),
                'median_peak_freq': np.median(all_ch1_peaks_freqs) if all_ch1_peaks_freqs else 0,
                'std_peak_freq': np.std(all_ch1_peaks_freqs) if all_ch1_peaks_freqs else 0,
            },
            'ch2': {
                'mean_mag': np.mean(all_ch2_mags),
                'std_mag': np.std(all_ch2_mags),
                'min_mag': np.min(all_ch2_mags),
                'max_mag': np.max(all_ch2_mags),
                'median_peak_freq': np.median(all_ch2_peaks_freqs) if all_ch2_peaks_freqs else 0,
                'std_peak_freq': np.std(all_ch2_peaks_freqs) if all_ch2_peaks_freqs else 0,
            },
            'n_samples': len(group_data)
        }
    
    def compute_group_differences(self, group1: str, group2: str) -> Dict:
        """Hitung perbedaan statistik antar group"""
        if group1 not in self.group_stats or group2 not in self.group_stats:
            return {}
        
        stats1 = self.group_stats[group1]
        stats2 = self.group_stats[group2]
        
        differences = {
            'ch1': {
                'mean_mag_diff': stats2['ch1']['mean_mag'] - stats1['ch1']['mean_mag'],
                'std_mag_diff': stats2['ch1']['std_mag'] - stats1['ch1']['std_mag'],
                'median_freq_diff': stats2['ch1']['median_peak_freq'] - stats1['ch1']['median_peak_freq'],
            },
            'ch2': {
                'mean_mag_diff': stats2['ch2']['mean_mag'] - stats1['ch2']['mean_mag'],
                'std_mag_diff': stats2['ch2']['std_mag'] - stats1['ch2']['std_mag'],
                'median_freq_diff': stats2['ch2']['median_peak_freq'] - stats1['ch2']['median_peak_freq'],
            }
        }
        
        return differences
    
    def toggle_group(self, group_name: str) -> bool:
        """Toggle group selection"""
        if group_name in self.selected_groups:
            self.selected_groups.remove(group_name)
            return False
        else:
            self.selected_groups.add(group_name)
            return True

analyzer = GroupAnalyzer()

# Callbacks
def toggle_group_callback(sender, app_data, user_data):
    """Callback untuk toggle group button"""
    group_name = user_data
    
    is_active = analyzer.toggle_group(group_name)
    
    if is_active:
        analyzer.load_group(group_name)
        dpg.configure_item(sender, label=f"✓ {group_name}")
    else:
        dpg.configure_item(sender, label=f"  {group_name}")
    
    update_all_visualizations()

def update_all_visualizations():
    """Update semua visualisasi"""
    # Clear plots
    clear_plot_series("ch1_overlay_yaxis")
    clear_plot_series("ch2_overlay_yaxis")
    
    # Clear tables
    clear_comparison_table()
    clear_stats_table()
    
    if not analyzer.selected_groups:
        return
    
    # Plot overlay untuk setiap group
    color_idx = 0
    for group_name in sorted(analyzer.selected_groups):
        if group_name not in analyzer.groups:
            continue
        
        group_data = analyzer.groups[group_name]
        group_color = GROUP_COLORS.get(group_name, SAMPLE_COLORS[color_idx % len(SAMPLE_COLORS)])
        
        # Compute average magnitude untuk group
        all_ch1_mags = []
        all_ch2_mags = []
        freqs_ch1 = None
        freqs_ch2 = None
        
        for filename, data in group_data.items():
            all_ch1_mags.append(data['mag_ch1'])
            all_ch2_mags.append(data['mag_ch2'])
            if freqs_ch1 is None:
                freqs_ch1 = data['freqs_ch1']
            if freqs_ch2 is None:
                freqs_ch2 = data['freqs_ch2']
        
        # Average magnitude
        avg_ch1_mag = np.mean(all_ch1_mags, axis=0)
        avg_ch2_mag = np.mean(all_ch2_mags, axis=0)
        
        # Add CH1 series
        ch1_series = dpg.add_line_series(
            freqs_ch1,
            avg_ch1_mag,
            label=f"{group_name} (avg)",
            parent="ch1_overlay_yaxis",
        )
        dpg.bind_item_theme(ch1_series, create_line_theme(group_color))
        
        # Add CH2 series
        ch2_series = dpg.add_line_series(
            freqs_ch2,
            avg_ch2_mag,
            label=f"{group_name} (avg)",
            parent="ch2_overlay_yaxis",
        )
        dpg.bind_item_theme(ch2_series, create_line_theme(group_color))
        
        color_idx += 1
    
    # Auto-fit axes
    dpg.fit_axis_data("ch1_overlay_xaxis")
    dpg.fit_axis_data("ch1_overlay_yaxis")
    dpg.fit_axis_data("ch2_overlay_xaxis")
    dpg.fit_axis_data("ch2_overlay_yaxis")
    
    # Update tables
    update_stats_table()
    if len(analyzer.selected_groups) >= 2:
        update_comparison_table()

def clear_plot_series(axis_tag):
    """Clear all series dari axis"""
    children = dpg.get_item_children(axis_tag, slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

def clear_comparison_table():
    """Clear comparison table"""
    if dpg.does_item_exist("comparison_table"):
        children = dpg.get_item_children("comparison_table", slot=1)
        if children:
            for child in children:
                dpg.delete_item(child)

def clear_stats_table():
    """Clear stats table"""
    if dpg.does_item_exist("stats_table"):
        children = dpg.get_item_children("stats_table", slot=1)
        if children:
            for child in children:
                dpg.delete_item(child)

def update_stats_table():
    """Update tabel statistik group"""
    if not dpg.does_item_exist("stats_table"):
        return
    
    for group_name in sorted(analyzer.selected_groups):
        if group_name not in analyzer.group_stats:
            continue
        
        stats = analyzer.group_stats[group_name]
        group_color = GROUP_COLORS.get(group_name, (200, 200, 200))
        
        # CH1 Stats
        with dpg.table_row(parent="stats_table"):
            dpg.add_text(f"{group_name} - CH1", color=group_color)
            dpg.add_text(f"{stats['ch1']['mean_mag']:.2f}")
            dpg.add_text(f"{stats['ch1']['std_mag']:.2f}")
            dpg.add_text(f"{stats['ch1']['median_peak_freq']:.2f}")
            dpg.add_text(f"{stats['n_samples']}")
        
        # CH2 Stats
        with dpg.table_row(parent="stats_table"):
            dpg.add_text(f"{group_name} - CH2", color=group_color)
            dpg.add_text(f"{stats['ch2']['mean_mag']:.2f}")
            dpg.add_text(f"{stats['ch2']['std_mag']:.2f}")
            dpg.add_text(f"{stats['ch2']['median_peak_freq']:.2f}")
            dpg.add_text(f"{stats['n_samples']}")

def update_comparison_table():
    """Update tabel perbandingan antar group"""
    if not dpg.does_item_exist("comparison_table"):
        return
    
    groups_list = sorted(list(analyzer.selected_groups))
    
    if len(groups_list) < 2:
        return
    
    # Compare first two selected groups
    group1, group2 = groups_list[0], groups_list[1]
    diffs = analyzer.compute_group_differences(group1, group2)
    
    if not diffs:
        return
    
    # CH1 Differences
    with dpg.table_row(parent="comparison_table"):
        dpg.add_text(f"{group1} vs {group2} - CH1")
        dpg.add_text(f"{diffs['ch1']['mean_mag_diff']:+.2f}")
        dpg.add_text(f"{diffs['ch1']['std_mag_diff']:+.2f}")
        dpg.add_text(f"{diffs['ch1']['median_freq_diff']:+.2f}")
    
    # CH2 Differences
    with dpg.table_row(parent="comparison_table"):
        dpg.add_text(f"{group1} vs {group2} - CH2")
        dpg.add_text(f"{diffs['ch2']['mean_mag_diff']:+.2f}")
        dpg.add_text(f"{diffs['ch2']['std_mag_diff']:+.2f}")
        dpg.add_text(f"{diffs['ch2']['median_freq_diff']:+.2f}")

def create_line_theme(color):
    """Create theme untuk line series"""
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
    return theme_id

def clear_all_callback():
    """Clear semua selected groups"""
    analyzer.selected_groups.clear()
    
    # Reset buttons
    available_groups = analyzer.discover_groups()
    for group_name in available_groups.keys():
        button_tag = f"btn_{group_name}"
        if dpg.does_item_exist(button_tag):
            dpg.configure_item(button_tag, label=f"  {group_name}")
    
    update_all_visualizations()

# Main UI
def create_group_comparison_panel():
    """Buat panel group comparison dengan DearPyGUI"""
    
    dpg.create_context()
    
    # Discover groups
    available_groups = analyzer.discover_groups()
    
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
    with dpg.window(label="Radar LPDP Group Comparison", tag="main_window", width=1600, height=950):
        
        dpg.add_text("📊 Group Comparison Analysis", color=(100, 200, 255))
        dpg.add_text("Select multiple groups to compare persamaan dalam group dan perbedaan antar group", 
                     color=(150, 150, 150))
        dpg.add_separator()
        
        # Top bar - Group toggle buttons
        with dpg.group(horizontal=True):
            dpg.add_text("📁 Groups:", color=(200, 200, 100))
            
            for group_name in sorted(available_groups.keys()):
                dpg.add_button(
                    label=f"  {group_name}",
                    callback=toggle_group_callback,
                    user_data=group_name,
                    tag=f"btn_{group_name}",
                    width=150
                )
            
            dpg.add_button(
                label="🗑️ Clear All",
                callback=clear_all_callback,
                width=100
            )
        
        dpg.add_separator()
        
        # Layout: 2 columns
        with dpg.group(horizontal=True):
            
            # Left column: Overlay Plots
            with dpg.child_window(width=1050, height=850):
                dpg.add_text("Group Average Comparison", color=(100, 200, 255))
                dpg.add_text("Overlay rata-rata FFT dari setiap group", color=(150, 150, 150))
                
                dpg.add_spacer(height=5)
                
                # CH1 Plot
                dpg.add_text("Channel 1 (CH1)", color=(255, 150, 100))
                with dpg.plot(label="CH1 Group Overlay", height=380, width=-1, tag="ch1_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="ch1_overlay_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="ch1_overlay_yaxis")
                
                dpg.add_spacer(height=10)
                
                # CH2 Plot
                dpg.add_text("Channel 2 (CH2)", color=(255, 200, 100))
                with dpg.plot(label="CH2 Group Overlay", height=380, width=-1, tag="ch2_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="ch2_overlay_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="ch2_overlay_yaxis")
            
            # Right column: Statistics & Comparison
            with dpg.child_window(width=500, height=850):
                dpg.add_text("Group Statistics & Comparison", color=(100, 255, 150))
                
                dpg.add_spacer(height=5)
                
                # Group Statistics Table
                dpg.add_text("📊 Group Statistics (Persamaan dalam Group)", color=(200, 200, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="stats_table",
                    height=350,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Group-CH", width_fixed=True, init_width_or_weight=120)
                    dpg.add_table_column(label="Mean Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Std Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Med Freq", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="N Samples", width_fixed=True, init_width_or_weight=80)
                
                dpg.add_spacer(height=10)
                
                # Group Comparison Table
                dpg.add_text("🔍 Group Differences (Perbedaan Antar Group)", color=(200, 100, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="comparison_table",
                    height=350,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Comparison", width_fixed=True, init_width_or_weight=120)
                    dpg.add_table_column(label="ΔMean Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="ΔStd Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="ΔMed Freq", width_fixed=True, init_width_or_weight=90)
        
        dpg.add_separator()
        dpg.add_text("💡 Tip: Pilih 2+ groups untuk melihat perbandingan. Setiap group menunjukkan rata-rata dari semua sample dalam group tersebut", 
                     color=(150, 150, 150))
    
    # Setup viewport
    dpg.create_viewport(title="Radar LPDP Group Comparison", width=1620, height=970)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    
    print("✅ Group comparison panel created!")
    print(f"📁 Found {len(available_groups)} groups")
    for group_name, files in available_groups.items():
        print(f"   - {group_name}: {len(files)} files")
    print("🚀 Click group buttons to load and compare")
    
    # Render loop
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()
    
    dpg.destroy_context()
    print("👋 Group comparison panel closed")

if __name__ == "__main__":
    print("="*60)
    print("🎯 Radar LPDP Group Comparison Analytics")
    print("="*60)
    print(f"📂 Sample directory: {SAMPLE_DIR}")
    
    available_groups = analyzer.discover_groups()
    print(f"📊 Available groups: {len(available_groups)}")
    for group_name, files in available_groups.items():
        print(f"   - {group_name}: {len(files)} files")
    print("="*60)
    
    create_group_comparison_panel()
