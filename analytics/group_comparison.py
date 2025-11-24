#!/usr/bin/env python3
"""
Radar LPDP Group Comparison Analytics
Analisis persamaan dalam group dan perbedaan antar group
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from collections import OrderedDict
import hashlib
from datetime import datetime
import numpy as np
import pandas as pd
import dearpygui.dearpygui as dpg

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from functions.data_processing import (
    load_and_process_data,
    compute_fft,
    compute_fft_linear,
    find_top_extrema,
)
from config import (
    SAMPLE_RATE,
    FFT_SMOOTHING_ENABLED,
    FFT_SMOOTHING_WINDOW,
    FFT_MAGNITUDE_MODE,
)

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
        self.export_peak_fields = {
            'index': True,
            'freq': True,
            'mag': True,
        }
        self.export_peak_count = 100
        self.export_channels = {
            'ch1': True,
            'ch2': True,
        }
        self.export_freq_range = (4000.0, 7000.0)
    
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
                
                # Compute FFT (dB) for analysis/peaks
                freqs_ch1_db, mag_ch1_db = compute_fft(
                    ch1, SAMPLE_RATE,
                    smooth=FFT_SMOOTHING_ENABLED,
                    smooth_window=FFT_SMOOTHING_WINDOW
                )
                freqs_ch2_db, mag_ch2_db = compute_fft(
                    ch2, SAMPLE_RATE,
                    smooth=FFT_SMOOTHING_ENABLED,
                    smooth_window=FFT_SMOOTHING_WINDOW
                )

                use_linear_display = FFT_MAGNITUDE_MODE.lower() == "linear"

                display_freqs_ch1, display_mag_ch1 = freqs_ch1_db, mag_ch1_db
                display_freqs_ch2, display_mag_ch2 = freqs_ch2_db, mag_ch2_db

                if use_linear_display:
                    display_freqs_ch1, display_mag_ch1 = compute_fft_linear(ch1, SAMPLE_RATE)
                    display_freqs_ch2, display_mag_ch2 = compute_fft_linear(ch2, SAMPLE_RATE)

                # Find peaks
                peak_limit = self.export_peak_count
                ch1_peaks, _ = find_top_extrema(freqs_ch1_db, mag_ch1_db, n_extrema=peak_limit)
                ch2_peaks, _ = find_top_extrema(freqs_ch2_db, mag_ch2_db, n_extrema=peak_limit)

                # Store data
                self.groups[group_name][filename] = {
                    'ch1_data': ch1,
                    'ch2_data': ch2,
                    'freqs_ch1': display_freqs_ch1,
                    'mag_ch1': display_mag_ch1,
                    'freqs_ch2': display_freqs_ch2,
                    'mag_ch2': display_mag_ch2,
                    'freqs_ch1_db': freqs_ch1_db,
                    'mag_ch1_db': mag_ch1_db,
                    'freqs_ch2_db': freqs_ch2_db,
                    'mag_ch2_db': mag_ch2_db,
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
        export_limit = max(1, self.export_peak_count)

        def compute_channel_stats(mags, peaks):
            peak_freqs = [p['freq_khz'] for p in peaks]
            sorted_peaks = sorted(peaks, key=lambda p: p['mag_db'], reverse=True)
            export_peaks = sorted_peaks[:export_limit]
            ui_peaks = export_peaks[:5]
            return {
                'mean_mag': np.mean(mags),
                'std_mag': np.std(mags),
                'min_mag': np.min(mags),
                'max_mag': np.max(mags),
                'median_peak_freq': np.median(peak_freqs) if peak_freqs else 0,
                'std_peak_freq': np.std(peak_freqs) if peak_freqs else 0,
                'top_peaks': ui_peaks,
                'export_peaks': export_peaks,
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
        peak_columns: "OrderedDict[Tuple[str, str], Dict[str, List[str]]]" = OrderedDict()
        max_peak_rank = 0

        sorted_groups = sorted(self.selected_groups)

        export_colors: Dict[str, Tuple[int, int, int]] = {}
        for color_idx, group_name in enumerate(sorted_groups):
            export_colors[group_name] = GROUP_COLORS.get(
                group_name,
                SAMPLE_COLORS[color_idx % len(SAMPLE_COLORS)]
            )

        for group_name in sorted_groups:
            stats = self.group_stats.get(group_name)
            if not stats:
                continue

            n_samples = stats.get('n_samples', 0)

            for ch_key, ch_label in [('ch1', 'CH1'), ('ch2', 'CH2')]:
                if not self.export_channels.get(ch_key, True):
                    continue
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
                peaks = ch_stats.get('export_peaks') or ch_stats.get('top_peaks', [])
                freq_min, freq_max = self.export_freq_range
                peaks = [p for p in peaks if freq_min <= (p.get('freq_khz') or 0) <= freq_max]
                peaks = peaks[:self.export_peak_count]
                max_peak_rank = max(max_peak_rank, len(peaks))

                column_key = (group_name, ch_label)
                chosen_metrics = [k for k, v in self.export_peak_fields.items() if v]
                column_data = {metric: [] for metric in chosen_metrics}

                for peak in peaks:
                    if 'index' in column_data:
                        column_data['index'].append(str(peak.get('index', '-')))
                    if 'freq' in column_data:
                        freq = peak.get('freq_khz')
                        column_data['freq'].append(f"{freq:.2f}" if freq is not None else "-")
                    if 'mag' in column_data:
                        mag = peak.get('mag_db')
                        column_data['mag'].append(f"{mag:.2f}" if mag is not None else "-")

                peak_columns[column_key] = column_data

        if not stats_rows:
            raise ValueError("Data statistik tidak tersedia untuk group terpilih")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            pd.DataFrame(stats_rows).to_excel(writer, sheet_name="Group Statistics", index=False)

            chosen_metrics = [k for k, v in self.export_peak_fields.items() if v]
            if max_peak_rank > 0 and peak_columns and chosen_metrics:
                # Pastikan semua kolom memiliki panjang yang sama dengan max_peak_rank
                peak_matrix = OrderedDict()
                peak_column_order: List[Tuple[str, str, str]] = []
                for column_key, value_dict in peak_columns.items():
                    for sub_key in ['index', 'freq', 'mag']:
                        if sub_key not in chosen_metrics:
                            continue
                        values = value_dict.get(sub_key, [])
                        if len(values) < max_peak_rank:
                            values = values + [""] * (max_peak_rank - len(values))
                        key = (column_key[0], column_key[1], sub_key)
                        peak_matrix[key] = values
                        peak_column_order.append(key)

                peak_df = pd.DataFrame(peak_matrix, index=range(1, max_peak_rank + 1))
                peak_df.index.name = "Peak Rank"
                peak_df.columns = pd.MultiIndex.from_tuples(peak_df.columns, names=["Group", "Channel", "Metric"])
                peak_df.to_excel(writer, sheet_name="Peak Details")

                workbook = writer.book
                worksheet = writer.sheets["Peak Details"]

                # Formats untuk header dan data
                index_header_fmt = workbook.add_format({
                    'bold': True,
                    'bg_color': '#303030',
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                data_fmt = workbook.add_format({'align': 'center'})

                worksheet.write(0, 0, "", index_header_fmt)
                worksheet.write(1, 0, "", index_header_fmt)
                worksheet.write(2, 0, "Peak Rank", index_header_fmt)
                worksheet.set_column(0, 0, 10, data_fmt)

                group_header_formats: Dict[str, any] = {}
                channel_header_formats: Dict[Tuple[str, str], any] = {}
                metric_header_formats: Dict[Tuple[str, str], any] = {}
                channel_data_formats: Dict[Tuple[str, str], any] = {}

                channel_style_factors = {
                    'CH1': {'channel': 0.45, 'metric': 0.65, 'data': 0.85},
                    'CH2': {'channel': 0.20, 'metric': 0.45, 'data': 0.70},
                }

                for col_idx, (group, channel, metric) in enumerate(peak_column_order):
                    excel_col = col_idx + 1  # offset karena kolom index
                    base_color = export_colors.get(group, (200, 200, 200))

                    if group not in group_header_formats:
                        group_header_formats[group] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(base_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })

                    style_factors = channel_style_factors.get(channel, channel_style_factors['CH1'])

                    if (group, channel) not in channel_header_formats:
                        channel_color = _lighten_color(base_color, style_factors['channel'])
                        channel_header_formats[(group, channel)] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(channel_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        metric_color = _lighten_color(base_color, style_factors['metric'])
                        metric_header_formats[(group, channel)] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(metric_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        data_color = _lighten_color(base_color, style_factors['data'])
                        channel_data_formats[(group, channel)] = workbook.add_format({
                            'align': 'center',
                            'bg_color': _rgb_to_hex(data_color),
                            'border': 1
                        })

                    worksheet.write(0, excel_col, group, group_header_formats[group])
                    worksheet.write(1, excel_col, channel, channel_header_formats[(group, channel)])
                    worksheet.write(2, excel_col, metric.capitalize(), metric_header_formats[(group, channel)])
                    worksheet.set_column(excel_col, excel_col, 14, channel_data_formats[(group, channel)])

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

def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
    """Convert RGB tuple ke format hex untuk Excel"""
    return "#{:02X}{:02X}{:02X}".format(*color)

def _lighten_color(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Lighten warna dengan faktor 0..1"""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in color)

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

def toggle_export_metric_callback(sender, app_data, user_data):
    """Toggle metric yang diexport untuk peak details"""
    analyzer.export_peak_fields[user_data] = bool(app_data)
    selected_metrics = [name for name, enabled in analyzer.export_peak_fields.items() if enabled]
    if not selected_metrics:
        dpg.set_value("export_status_text", "⚠️ Tidak ada metric peak terpilih. Hanya statistik group yang akan diexport.")
    else:
        dpg.set_value("export_status_text", "")

def toggle_export_channel_callback(sender, app_data, user_data):
    """Toggle channel yang diikutkan pada ekspor"""
    analyzer.export_channels[user_data] = bool(app_data)
    selected_channels = [name for name, enabled in analyzer.export_channels.items() if enabled]
    if not selected_channels:
        dpg.set_value("export_status_text", "⚠️ Minimal pilih satu channel untuk ekspor peak details.")
    else:
        dpg.set_value("export_status_text", "")

def update_export_freq_range_callback(sender, app_data, user_data):
    """Update rentang frekuensi untuk filter peak eksport"""
    current_min, current_max = analyzer.export_freq_range
    try:
        value = float(app_data)
    except (TypeError, ValueError):
        value = current_min if user_data == "min" else current_max

    if user_data == "min":
        new_min, new_max = value, current_max
    else:
        new_min, new_max = current_min, value

    if new_min > new_max:
        new_min, new_max = new_max, new_min

    analyzer.export_freq_range = (new_min, new_max)
    dpg.set_value("export_status_text", f"ℹ️ Peak diekspor untuk frekuensi {new_min:.0f}-{new_max:.0f} kHz.")

def update_export_peak_count_callback(sender, app_data):
    """Update jumlah peak yang akan diexport"""
    try:
        value = int(app_data)
    except (TypeError, ValueError):
        value = analyzer.export_peak_count
    if value <= 0:
        value = 100
    analyzer.export_peak_count = value
    # Recompute stats untuk group yang sudah dimuat agar list export_peaks tersinkron
    for group_name in list(analyzer.groups.keys()):
        if analyzer.groups[group_name]:
            analyzer._compute_group_stats(group_name)
    update_all_visualizations()
    dpg.set_value("export_status_text", f"ℹ️ Peak export count diset ke {value}. Reload group jika ingin data > {value}.")

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
            dpg.add_text("Peak fields:", color=(180, 180, 180))
            dpg.add_checkbox(label="Index", default_value=True, callback=toggle_export_metric_callback, user_data="index")
            dpg.add_checkbox(label="Freq", default_value=True, callback=toggle_export_metric_callback, user_data="freq")
            dpg.add_checkbox(label="Mag", default_value=True, callback=toggle_export_metric_callback, user_data="mag")
            dpg.add_spacer(width=10)
            dpg.add_text("Channels:", color=(180, 180, 180))
            dpg.add_checkbox(label="CH1", default_value=True, callback=toggle_export_channel_callback, user_data="ch1")
            dpg.add_checkbox(label="CH2", default_value=True, callback=toggle_export_channel_callback, user_data="ch2")
            dpg.add_spacer(width=10)
            dpg.add_text("Freq (kHz):", color=(180, 180, 180))
            dpg.add_input_float(label="Min", width=80, default_value=analyzer.export_freq_range[0], format="%.0f",
                                callback=update_export_freq_range_callback, user_data="min")
            dpg.add_input_float(label="Max", width=80, default_value=analyzer.export_freq_range[1], format="%.0f",
                                callback=update_export_freq_range_callback, user_data="max")
            dpg.add_input_int(label="Peak count", width=90, min_value=1, default_value=analyzer.export_peak_count,
                              callback=update_export_peak_count_callback, step=5)
            dpg.add_spacer(width=10)
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
