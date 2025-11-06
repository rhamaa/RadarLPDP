#!/usr/bin/env python3
"""
Radar LPDP Group Comparison Analytics
Analisis persamaan dalam group dan perbedaan antar group
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import OrderedDict
import hashlib
from datetime import datetime
import numpy as np
import pandas as pd
import dearpygui.dearpygui as dpg

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from functions.data_processing import load_and_process_data, compute_fft, find_top_extrema
from config import SAMPLE_RATE, FFT_SMOOTHING_ENABLED, FFT_SMOOTHING_WINDOW

# Configuration
SAMPLE_DIR = Path(__file__).parent / "sample"
EXPORT_DIR = Path(__file__).parent / "exports"
DEFAULT_LAYOUT_SPLIT = 70  # percent allocated to plot column

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
        self.group_filter = ""
        self.suppress_group_checkbox = False
    
    def discover_groups(self):
        """Discover semua group dari direktori sample (recursive)"""
        groups = {}
        
        # Cari semua subfolder yang mengandung .bin files
        for bin_file in SAMPLE_DIR.glob("**/*.bin"):
            # Gunakan parent folder sebagai group name
            group_dir = bin_file.parent
            group_name = str(group_dir.relative_to(SAMPLE_DIR)).replace("\\", "/")
            
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(bin_file)
        
        # Sort files dalam setiap group
        for group_name in groups:
            groups[group_name] = sorted(groups[group_name])
            print(f"📂 Found group: {group_name} ({len(groups[group_name])} files)")
        
        return groups
    
    def load_group(self, group_name: str):
        """Load semua sample dalam group"""
        # Handle path separator untuk cross-platform
        group_path = SAMPLE_DIR / group_name.replace("/", "\\" if Path("").drive else "/")
        
        if not group_path.exists():
            print(f"❌ Group not found: {group_name}")
            return False
        
        bin_files = sorted(list(group_path.glob("*.bin")))
        if not bin_files:
            print(f"❌ No .bin files in {group_name}")
            return False
        
        print(f"📂 Loading group: {group_name}")
        self.groups[group_name] = {}
        
        for filepath in bin_files:
            # Gunakan relative path dari SAMPLE_DIR sebagai identifier
            filename = str(filepath.relative_to(SAMPLE_DIR)).replace("\\", "/")
            
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
                ch1_peaks, _ = find_top_extrema(freqs_ch1, mag_ch1, n_extrema=8)
                ch2_peaks, _ = find_top_extrema(freqs_ch2, mag_ch2, n_extrema=8)
                
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
    
    def _compute_group_stats(self, group_name: str):
        """Compute statistik untuk group"""
        if group_name not in self.groups or not self.groups[group_name]:
            return
        
        group_data = self.groups[group_name]
        
        # Collect magnitudes dan peaks dari semua file
        all_ch1_mags, all_ch2_mags = [], []
        all_ch1_peaks, all_ch2_peaks = [], []
        
        for data in group_data.values():
            all_ch1_mags.extend(data['mag_ch1'])
            all_ch2_mags.extend(data['mag_ch2'])
            all_ch1_peaks.extend(data['ch1_peaks'])
            all_ch2_peaks.extend(data['ch2_peaks'])
        
        # Helper untuk compute channel stats
        def compute_channel_stats(mags, peaks):
            peak_freqs = [p['freq_khz'] for p in peaks]
            top_peaks = sorted(peaks, key=lambda p: p['mag_db'], reverse=True)[:5]
            return {
                'mean_mag': np.mean(mags),
                'std_mag': np.std(mags),
                'min_mag': np.min(mags),
                'max_mag': np.max(mags),
                'median_peak_freq': np.median(peak_freqs) if peak_freqs else 0,
                'std_peak_freq': np.std(peak_freqs) if peak_freqs else 0,
                'top_peaks': top_peaks,
            }
        
        self.group_stats[group_name] = {
            'ch1': compute_channel_stats(all_ch1_mags, all_ch1_peaks),
            'ch2': compute_channel_stats(all_ch2_mags, all_ch2_peaks),
            'n_samples': len(group_data)
        }

    def export_selected_to_excel(self, filepath: Path):
        """Export statistik dan peak detail dari group terpilih ke Excel"""
        if not self.selected_groups:
            raise ValueError("Tidak ada group yang dipilih")

        stats_rows: List[Dict] = []
        peak_columns: "OrderedDict[Tuple[str, str], Dict[str, List[str]]" = OrderedDict()
        max_peak_rank = 0

        for group_name in sorted(self.selected_groups):
            stats = self.group_stats.get(group_name)
            if not stats:
                continue

            n_samples = stats.get('n_samples', 0)

            for ch_key, ch_label in [('ch1', 'CH1'), ('ch2', 'CH2')]:
                ch_stats = stats.get(ch_key)
                if not ch_stats:
                    continue

                stats_rows.append({
                    'Group': group_name,
                    'Channel': ch_label,
                    'Mean Mag (dB)': ch_stats.get('mean_mag'),
                    'Std Mag (dB)': ch_stats.get('std_mag'),
                    'Min Mag (dB)': ch_stats.get('min_mag'),
                    'Max Mag (dB)': ch_stats.get('max_mag'),
                    'Median Peak Freq (kHz)': ch_stats.get('median_peak_freq'),
                    'Std Peak Freq (kHz)': ch_stats.get('std_peak_freq'),
                    'N Samples': n_samples,
                })

                # Format peak data untuk export matrix (sesuai contoh)
                peaks = ch_stats.get('top_peaks', [])
                max_peak_rank = max(max_peak_rank, len(peaks))

                column_key = (group_name, ch_label)
                column_data = {
                    'index': [],
                    'freq': [],
                    'mag': [],
                }

                for peak in peaks:
                    column_data['index'].append(str(peak.get('index', '-')))
                    freq = peak.get('freq_khz')
                    mag = peak.get('mag_db')
                    column_data['freq'].append(f"{freq:.2f}" if freq is not None else "-")
                    column_data['mag'].append(f"{mag:.2f}" if mag is not None else "-")

                peak_columns[column_key] = column_data

        if not stats_rows:
            raise ValueError("Data statistik tidak tersedia untuk group terpilih")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            pd.DataFrame(stats_rows).to_excel(writer, sheet_name="Group Statistics", index=False)

            if max_peak_rank > 0 and peak_columns:
                # Pastikan semua kolom memiliki panjang yang sama dengan max_peak_rank
                peak_matrix = OrderedDict()
                for column_key, value_dict in peak_columns.items():
                    for sub_key in ['index', 'freq', 'mag']:
                        values = value_dict.get(sub_key, [])
                        if len(values) < max_peak_rank:
                            values = values + [""] * (max_peak_rank - len(values))
                        peak_matrix[(column_key[0], column_key[1], sub_key)] = values

                peak_df = pd.DataFrame(peak_matrix, index=range(1, max_peak_rank + 1))
                peak_df.index.name = "Peak Rank"
                peak_df.columns = pd.MultiIndex.from_tuples(peak_df.columns, names=["Group", "Channel", "Metric"])
                peak_df.to_excel(writer, sheet_name="Peak Details")

    def toggle_group(self, group_name: str) -> bool:
        """Toggle group selection"""
        if group_name in self.selected_groups:
            self.selected_groups.remove(group_name)
            return False
        else:
            self.selected_groups.add(group_name)
            return True

analyzer = GroupAnalyzer()

# Color mapping untuk konsistensi antara plot dan tabel
_group_color_cache = {}  # {group_name: color}

def get_group_color(group_name: str, color_idx: int = None) -> Tuple[int, int, int]:
    """Get warna untuk group dengan caching untuk konsistensi"""
    if group_name in _group_color_cache:
        return _group_color_cache[group_name]
    
    # Cek GROUP_COLORS dulu
    if group_name in GROUP_COLORS:
        color = GROUP_COLORS[group_name]
    else:
        # Gunakan SAMPLE_COLORS dengan index
        if color_idx is None:
            color_idx = len(_group_color_cache) % len(SAMPLE_COLORS)
        color = SAMPLE_COLORS[color_idx]
    
    _group_color_cache[group_name] = color
    return color

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
    """Update semua visualisasi dengan warna konsisten"""
    # Clear semua elemen
    for axis in ["ch1_overlay_yaxis", "ch2_overlay_yaxis"]:
        clear_plot_series(axis)
    for table in ["stats_table", "peak_detail_table"]:
        clear_table(table)
    
    if not analyzer.selected_groups:
        return
    
    # Clear color cache untuk reset
    _group_color_cache.clear()
    
    # Plot overlay untuk setiap group dengan color index tracking
    for color_idx, group_name in enumerate(sorted(analyzer.selected_groups)):
        if group_name not in analyzer.groups:
            continue
        
        group_data = analyzer.groups[group_name]
        # Gunakan get_group_color dengan color_idx untuk konsistensi
        group_color = get_group_color(group_name, color_idx)
        
        # Collect magnitudes dan frequencies
        mags_ch1, mags_ch2 = [], []
        freqs_ch1 = freqs_ch2 = None
        
        for data in group_data.values():
            mags_ch1.append(data['mag_ch1'])
            mags_ch2.append(data['mag_ch2'])
            if freqs_ch1 is None:
                freqs_ch1, freqs_ch2 = data['freqs_ch1'], data['freqs_ch2']
        
        # Plot average magnitudes dengan warna yang di-cache
        _plot_channel_series(freqs_ch1, np.mean(mags_ch1, axis=0), group_name, 
                            "ch1_overlay_yaxis", group_color)
        _plot_channel_series(freqs_ch2, np.mean(mags_ch2, axis=0), group_name, 
                            "ch2_overlay_yaxis", group_color)
    
    # Auto-fit axes
    for axis in ["ch1_overlay_xaxis", "ch1_overlay_yaxis", "ch2_overlay_xaxis", "ch2_overlay_yaxis"]:
        dpg.fit_axis_data(axis)
    
    # Update tables dengan warna yang sudah di-cache
    update_stats_table()
    update_peak_detail_table()

def _plot_channel_series(freqs, mags, label, parent_axis, color):
    """Helper untuk plot series dengan theme"""
    series = dpg.add_line_series(freqs, mags, label=f"{label} (avg)", parent=parent_axis)
    dpg.bind_item_theme(series, create_line_theme(color))

def clear_plot_series(axis_tag):
    """Clear all series dari axis"""
    children = dpg.get_item_children(axis_tag, slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

def clear_table(table_tag):
    """Clear rows dari table"""
    if dpg.does_item_exist(table_tag):
        children = dpg.get_item_children(table_tag, slot=1)
        if children:
            for child in children:
                dpg.delete_item(child)

def update_stats_table():
    """Update tabel statistik group dengan warna dari cache"""
    if not dpg.does_item_exist("stats_table"):
        return
    
    for group_name in sorted(analyzer.selected_groups):
        if group_name not in analyzer.group_stats:
            continue
        
        stats = analyzer.group_stats[group_name]
        # Gunakan cached color untuk konsistensi dengan plot
        group_color = _group_color_cache.get(group_name, (200, 200, 200))
        
        # Add rows untuk CH1 dan CH2
        for ch, label in [('ch1', 'CH1'), ('ch2', 'CH2')]:
            with dpg.table_row(parent="stats_table"):
                dpg.add_text(f"{group_name} - {label}", color=group_color)
                dpg.add_text(f"{stats[ch]['mean_mag']:.2f}")
                dpg.add_text(f"{stats[ch]['std_mag']:.2f}")
                dpg.add_text(f"{stats[ch]['median_peak_freq']:.2f}")
                dpg.add_text(f"{stats['n_samples']}")

def update_peak_detail_table():
    """Update tabel detail peak dengan index dan warna konsisten"""
    if not dpg.does_item_exist("peak_detail_table"):
        return
    
    for group_name in sorted(analyzer.selected_groups):
        stats = analyzer.group_stats.get(group_name)
        if not stats:
            continue
        
        # Gunakan cached color untuk konsistensi dengan plot
        group_color = _group_color_cache.get(group_name, (200, 200, 200))
        for ch, label in [('ch1', 'CH1'), ('ch2', 'CH2')]:
            for idx, peak in enumerate(stats[ch].get('top_peaks', []), start=1):
                with dpg.table_row(parent="peak_detail_table"):
                    dpg.add_text(group_name, color=group_color)
                    dpg.add_text(label)
                    dpg.add_text(f"#{idx}")
                    dpg.add_text(str(peak.get('index', '-')))
                    dpg.add_text(f"{peak.get('freq_khz', 0):.2f}")
                    dpg.add_text(f"{peak.get('mag_db', 0):.2f}")

def create_line_theme(color):
    """Create theme untuk line series"""
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
    return theme_id

def clear_all_callback():
    """Clear semua selected groups"""
    analyzer.selected_groups.clear()
    
    analyzer.suppress_group_checkbox = True
    try:
        for rel_path in analyzer.groups.keys():
            tag = f"group_chk_{hashlib.md5(rel_path.encode()).hexdigest()}"
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, False)
    finally:
        analyzer.suppress_group_checkbox = False
    
    update_all_visualizations()

def export_to_excel_callback():
    """Export data statistik dan peak ke file Excel"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = EXPORT_DIR / f"group_comparison_{timestamp}.xlsx"
    try:
        analyzer.export_selected_to_excel(filepath)
        dpg.set_value("export_status_text", f"✅ Exported to {filepath}")
    except ValueError as err:
        dpg.set_value("export_status_text", f"⚠️ {err}")
    except Exception as exc:
        dpg.set_value("export_status_text", f"❌ Export failed: {exc}")

def update_layout_split():
    """Update layout split ratio berdasarkan slider value"""
    viewport_width = dpg.get_viewport_client_width()
    available_width = max(viewport_width - 60, 400)
    split_percent = DEFAULT_LAYOUT_SPLIT
    left_width = int(available_width * split_percent / 100)
    right_width = available_width - left_width
    if dpg.does_item_exist("left_column"):
        dpg.configure_item("left_column", width=left_width, height=-1)
    if dpg.does_item_exist("right_column"):
        dpg.configure_item("right_column", width=right_width, height=-1)


def viewport_resize_callback(sender, app_data):
    update_layout_split()

def _build_group_tree(filter_text: str):
    tree = {}
    normalized_filter = filter_text.lower()
    for group_name in analyzer.groups.keys():
        rel_parts = group_name.split("/") if group_name else []
        if normalized_filter and normalized_filter not in group_name.lower():
            continue
        node = tree
        for part in rel_parts[:-1]:
            node = node.setdefault(part, {})
        leaf_list = node.setdefault("__groups__", [])
        if group_name not in leaf_list:
            leaf_list.append(group_name)
    return tree

def _render_group_tree(tree, parent, depth=0):
    directories = sorted(k for k in tree.keys() if k != "__groups__")
    for directory in directories:
        node_id = dpg.add_tree_node(
            label=directory,
            parent=parent,
            default_open=(depth == 0)
        )
        _render_group_tree(tree[directory], node_id, depth + 1)
    leaf_groups = sorted(tree.get("__groups__", []))
    for group_name in leaf_groups:
        tag = f"group_chk_{hashlib.md5(group_name.encode()).hexdigest()}"
        checkbox_id = dpg.add_checkbox(
            label=group_name.split("/")[-1],
            parent=parent,
            default_value=(group_name in analyzer.selected_groups),
            callback=group_checkbox_callback,
            user_data=group_name,
            tag=tag
        )
        with dpg.tooltip(checkbox_id):
            dpg.add_text(group_name)

def update_group_tree_ui():
    if not dpg.does_item_exist("group_tree_container"):
        return
    dpg.delete_item("group_tree_container", children_only=True)
    tree = _build_group_tree(analyzer.group_filter)
    if not tree:
        dpg.add_text("No groups found", parent="group_tree_container", color=(200, 100, 100))
        return
    _render_group_tree(tree, "group_tree_container")

def group_search_callback(sender, app_data, user_data):
    analyzer.group_filter = app_data.strip()
    update_group_tree_ui()

def clear_group_filter_callback():
    analyzer.group_filter = ""
    if dpg.does_item_exist("group_search_input"):
        dpg.set_value("group_search_input", "")
    update_group_tree_ui()

def group_checkbox_callback(sender, app_data, user_data):
    if analyzer.suppress_group_checkbox:
        return
    group_name = user_data
    if app_data:
        if analyzer.toggle_group(group_name):
            analyzer.load_group(group_name)
    else:
        if group_name in analyzer.selected_groups:
            analyzer.selected_groups.remove(group_name)
    update_all_visualizations()

# Main UI
def create_group_comparison_panel():
    """Buat panel group comparison dengan DearPyGUI"""
    
    dpg.create_context()
    
    # Discover groups
    available_groups = analyzer.discover_groups()
    analyzer.groups = {name: {} for name in available_groups.keys()}
    
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
    with dpg.window(label="Radar LPDP Group Comparison", tag="main_window", no_close=False):
        
        dpg.add_text("📊 Group Comparison Analysis", color=(100, 200, 255))
        dpg.add_text("Use the group explorer to control which groups are compared", 
                     color=(150, 150, 150))
        dpg.add_separator()
        
        with dpg.collapsing_header(label="📁 Group Explorer", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    label="Search",
                    tag="group_search_input",
                    width=260,
                    hint="Filter group name",
                    callback=group_search_callback,
                    user_data=None
                )
                dpg.add_button(label="Reset", width=70, callback=clear_group_filter_callback)
                dpg.add_button(label="🗑️ Clear", width=80, callback=clear_all_callback)
            with dpg.child_window(tag="group_tree_container", height=170, width=-1, border=True):
                dpg.add_text("Loading groups...")
        
        dpg.add_separator()
        
        dpg.add_text("Layout menggunakan rasio tetap untuk plot dan statistik", color=(120, 120, 120))
        dpg.add_separator()
        
        # Layout: 2 columns
        with dpg.group(horizontal=True, tag="main_layout_group"):
            
            # Left column: Overlay Plots
            with dpg.child_window(tag="left_column", border=False):
                dpg.add_text("Group Average Comparison", color=(100, 200, 255))
                dpg.add_text("Overlay rata-rata FFT dari setiap group", color=(150, 150, 150))
                
                dpg.add_spacer(height=5)
                
                # CH1 Plot
                dpg.add_text("Channel 1 (CH1)", color=(255, 150, 100))
                with dpg.plot(label="CH1 Group Overlay", height=360, width=-1, tag="ch1_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="ch1_overlay_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="ch1_overlay_yaxis")
                
                dpg.add_spacer(height=10)
                
                # CH2 Plot
                dpg.add_text("Channel 2 (CH2)", color=(255, 200, 100))
                with dpg.plot(label="CH2 Group Overlay", height=360, width=-1, tag="ch2_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="ch2_overlay_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="ch2_overlay_yaxis")
            
            # Right column: Statistics & Peaks
            with dpg.child_window(tag="right_column", border=False):
                dpg.add_text("Group Statistics", color=(100, 255, 150))
                
                dpg.add_spacer(height=5)
                
                # Group Statistics Table
                dpg.add_text("📊 Group Statistics (Persamaan dalam Group)", color=(200, 200, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    resizable=True,
                    policy=dpg.mvTable_SizingFixedFit,
                    tag="stats_table",
                    height=220,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Group-CH", width_fixed=True, init_width_or_weight=120)
                    dpg.add_table_column(label="Mean Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Std Mag", width_fixed=True, init_width_or_weight=90)
                    dpg.add_table_column(label="Med Freq", width_fixed=True, init_width_or_weight=75)
                    dpg.add_table_column(label="N Samples", width_fixed=True, init_width_or_weight=65)
                
                dpg.add_spacer(height=8)
                dpg.add_text("📌 Peak Details", color=(200, 200, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    resizable=True,
                    policy=dpg.mvTable_SizingFixedFit,
                    tag="peak_detail_table",
                    height=220,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Group", width_fixed=True, init_width_or_weight=120)
                    dpg.add_table_column(label="Channel", width_fixed=True, init_width_or_weight=60)
                    dpg.add_table_column(label="Rank", width_fixed=True, init_width_or_weight=45)
                    dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=60)
                    dpg.add_table_column(label="Freq (kHz)", width_fixed=True, init_width_or_weight=80)
                    dpg.add_table_column(label="Mag (dB)", width_fixed=True, init_width_or_weight=80)
        
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(label="💾 Export to Excel", callback=export_to_excel_callback)
            dpg.add_text("", tag="export_status_text", color=(180, 180, 180))
        dpg.add_text("💡 Tip: Checklist satu atau beberapa group untuk melihat rata-rata FFT beserta statistiknya.", 
                     color=(150, 150, 150))
    
    # Setup viewport
    dpg.create_viewport(title="Radar LPDP Group Comparison", width=1920, height=1080)
    dpg.setup_dearpygui()
    dpg.set_viewport_resize_callback(viewport_resize_callback)
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    dpg.configure_item("main_window", pos=(0, 0), width=-1, height=-1)
    update_group_tree_ui()
    update_layout_split()
    
    print("✅ Group comparison panel created!")
    print(f"📁 Found {len(available_groups)} groups")
    for group_name, files in available_groups.items():
        print(f"   - {group_name}: {len(files)} files")
    print("🚀 Use the group explorer to load and compare")
    
    # Render loop
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()
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
