#!/usr/bin/env python3
"""
Radar LPDP Analytics Tool
Interactive panel untuk analisis sample data radar dengan toggle buttons
"""

import sys
from pathlib import Path
import hashlib
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import numpy as np
import pandas as pd
import dearpygui.dearpygui as dpg
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
AVAILABLE_FILES = sorted(list(SAMPLE_DIR.glob("**/*.bin")))

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


def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
    """Convert RGB tuple ke format hex"""
    return "#{:02X}{:02X}{:02X}".format(*color)


def _lighten_color(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Lighten warna dengan faktor 0..1"""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in color)

# Global state
class AnalyticsState:
    def __init__(self):
        self.active_samples = {}  # {filename: {data, color, visible}}
        self.next_color_index = 0
        self.enable_nulling = True  # Enable data nulling below 10th peak
        self.nulling_threshold_rank = 10  # Null data below this peak rank
        self.sample_filter = ""
        self.suppress_checkbox_callback = False
        self.export_peak_fields: Dict[str, bool] = {
            'index': True,
            'freq': True,
            'mag': True,
        }
        self.export_peak_count = 100
        self.export_channels: Dict[str, bool] = {
            'ch1': True,
            'ch2': True,
        }
        self.export_freq_range: Tuple[float, float] = (4000.0, 7000.0)
    
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
        # Handle both relative path (from subfolder) and direct filename
        filepath = SAMPLE_DIR / filename if not Path(filename).is_absolute() else Path(filename)
        
        if not filepath.exists():
            print(f"❌ File not found: {filepath}")
            return
        
        print(f"📂 Loading: {filename}")
        
        # Load data
        ch1, ch2, n_samples, sr = load_and_process_data(str(filepath), SAMPLE_RATE)
        
        if ch1 is None:
            print(f"❌ Failed to load {filename}")
            return
        
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

        # Determine display spectrum based on config mode
        display_freqs_ch1, display_mag_ch1 = freqs_ch1_db, mag_ch1_db
        display_freqs_ch2, display_mag_ch2 = freqs_ch2_db, mag_ch2_db
        use_linear_display = FFT_MAGNITUDE_MODE.lower() == "linear"

        if use_linear_display:
            display_freqs_ch1, display_mag_ch1 = compute_fft_linear(ch1, SAMPLE_RATE)
            display_freqs_ch2, display_mag_ch2 = compute_fft_linear(ch2, SAMPLE_RATE)

        peak_limit = max(self.export_peak_count, 20)
        # Find peaks (get more untuk nulling / ekspor)
        ch1_peaks, _ = find_top_extrema(freqs_ch1_db, mag_ch1_db, n_extrema=peak_limit)
        ch2_peaks, _ = find_top_extrema(freqs_ch2_db, mag_ch2_db, n_extrema=peak_limit)

        mag_ch1_display = mag_ch1_db
        mag_ch2_display = mag_ch2_db

        # Apply data nulling jika enabled
        if not use_linear_display:
            if self.enable_nulling and len(ch1_peaks) > self.nulling_threshold_rank:
                mag_ch1_display = self._apply_nulling(mag_ch1_db, ch1_peaks, self.nulling_threshold_rank)
            if self.enable_nulling and len(ch2_peaks) > self.nulling_threshold_rank:
                mag_ch2_display = self._apply_nulling(mag_ch2_db, ch2_peaks, self.nulling_threshold_rank)

        if use_linear_display:
            mag_ch1_display = display_mag_ch1
            mag_ch2_display = display_mag_ch2

        # Assign color
        color = SAMPLE_COLORS[self.next_color_index % len(SAMPLE_COLORS)]
        self.next_color_index += 1
        
        # Store data
        self.active_samples[filename] = {
            'ch1_data': ch1,
            'ch2_data': ch2,
            'freqs_ch1': display_freqs_ch1,
            'mag_ch1_raw': mag_ch1_db,
            'mag_ch1': mag_ch1_display,
            'freqs_ch2': display_freqs_ch2,
            'mag_ch2_raw': mag_ch2_db,
            'mag_ch2': mag_ch2_display,
            'freqs_ch1_db': freqs_ch1_db,
            'mag_ch1_db': mag_ch1_db,
            'freqs_ch2_db': freqs_ch2_db,
            'mag_ch2_db': mag_ch2_db,
            'ch1_peaks': ch1_peaks,
            'ch2_peaks': ch2_peaks,
            'color': color,
            'n_samples': n_samples
        }

        print(f"✅ Loaded {filename}: {n_samples} samples, {len(ch1_peaks)} CH1 peaks, {len(ch2_peaks)} CH2 peaks")
    
    def _apply_nulling(self, magnitudes, peaks, threshold_rank):
        """Null data dibawah peak rank tertentu"""
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

    def refresh_active_sample_peaks(self):
        """Recompute peak list untuk semua sample aktif sesuai konfigurasi"""
        if not self.active_samples:
            return
        peak_limit = max(self.export_peak_count, 20)
        for sample_data in self.active_samples.values():
            freqs_ch1 = sample_data['freqs_ch1']
            mag_ch1_raw = sample_data.get('mag_ch1_raw', sample_data['mag_ch1'])
            freqs_ch2 = sample_data['freqs_ch2']
            mag_ch2_raw = sample_data.get('mag_ch2_raw', sample_data['mag_ch2'])

            ch1_peaks, _ = find_top_extrema(freqs_ch1, mag_ch1_raw, n_extrema=peak_limit)
            ch2_peaks, _ = find_top_extrema(freqs_ch2, mag_ch2_raw, n_extrema=peak_limit)

            sample_data['ch1_peaks'] = ch1_peaks
            sample_data['ch2_peaks'] = ch2_peaks

    def export_active_to_excel(self, filepath: Path):
        """Export statistik dan peak detail dari sample aktif ke Excel"""
        if not self.active_samples:
            raise ValueError("Tidak ada sample aktif")

        chosen_channels = [key for key, enabled in self.export_channels.items() if enabled]
        if not chosen_channels:
            raise ValueError("Minimal pilih satu channel untuk diexport")

        chosen_metrics = [key for key, enabled in self.export_peak_fields.items() if enabled]

        stats_rows: List[Dict[str, Any]] = []
        peak_columns: "OrderedDict[Tuple[str, str], Dict[str, List[str]]]" = OrderedDict()
        max_peak_rank = 0

        freq_min, freq_max = self.export_freq_range
        peak_limit = self.export_peak_count

        export_colors: Dict[str, Tuple[int, int, int]] = {}

        for filename in sorted(self.active_samples.keys()):
            sample_data = self.active_samples[filename]
            export_colors[filename] = sample_data['color']

            for ch_key, ch_label in [('ch1', 'CH1'), ('ch2', 'CH2')]:
                if ch_key not in chosen_channels:
                    continue

                mag_raw = sample_data['mag_ch1_raw'] if ch_key == 'ch1' else sample_data['mag_ch2_raw']
                mag_array = np.asarray(mag_raw)
                peaks = sample_data.get(f"{ch_key}_peaks", [])

                filtered_peaks = [
                    peak for peak in peaks
                    if freq_min <= (peak.get('freq_khz') or 0) <= freq_max
                ][:peak_limit]

                max_peak_rank = max(max_peak_rank, len(filtered_peaks))

                peak_freqs = [peak.get('freq_khz') for peak in filtered_peaks]

                stats_rows.append({
                    'Sample': filename,
                    'Channel': ch_label,
                    'Mean Mag (dB)': float(np.mean(mag_array)) if mag_array.size else None,
                    'Std Mag (dB)': float(np.std(mag_array)) if mag_array.size else None,
                    'Min Mag (dB)': float(np.min(mag_array)) if mag_array.size else None,
                    'Max Mag (dB)': float(np.max(mag_array)) if mag_array.size else None,
                    'Median Peak Freq (kHz)': float(np.median(peak_freqs)) if peak_freqs else None,
                    'Std Peak Freq (kHz)': float(np.std(peak_freqs)) if len(peak_freqs) > 1 else 0.0,
                    'Peak Count (range)': len(filtered_peaks),
                    'N Samples': sample_data.get('n_samples', 0),
                })

                if not chosen_metrics:
                    continue

                column_key = (filename, ch_label)
                column_data = {metric: [] for metric in chosen_metrics}

                for peak in filtered_peaks:
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
            raise ValueError("Tidak ada data untuk diexport")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            pd.DataFrame(stats_rows).to_excel(writer, sheet_name="Sample Statistics", index=False)

            if max_peak_rank > 0 and peak_columns and chosen_metrics:
                peak_matrix = OrderedDict()
                peak_column_order: List[Tuple[str, str, str]] = []
                for column_key, value_dict in peak_columns.items():
                    for metric in ['index', 'freq', 'mag']:
                        if metric not in chosen_metrics:
                            continue
                        values = value_dict.get(metric, [])
                        if len(values) < max_peak_rank:
                            values = values + [""] * (max_peak_rank - len(values))
                        key = (column_key[0], column_key[1], metric)
                        peak_matrix[key] = values
                        peak_column_order.append(key)

                peak_df = pd.DataFrame(peak_matrix, index=range(1, max_peak_rank + 1))
                peak_df.index.name = "Peak Rank"
                peak_df.columns = pd.MultiIndex.from_tuples(peak_df.columns, names=["Sample", "Channel", "Metric"])
                peak_df.to_excel(writer, sheet_name="Peak Details")

                workbook = writer.book
                worksheet = writer.sheets["Peak Details"]

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
                worksheet.set_column(0, 0, 11, data_fmt)

                sample_header_formats: Dict[str, Any] = {}
                channel_header_formats: Dict[Tuple[str, str], Any] = {}
                metric_header_formats: Dict[Tuple[str, str], Any] = {}
                channel_data_formats: Dict[Tuple[str, str], Any] = {}

                channel_style_factors = {
                    'CH1': {'channel': 0.45, 'metric': 0.65, 'data': 0.85},
                    'CH2': {'channel': 0.20, 'metric': 0.45, 'data': 0.70},
                }

                for col_idx, (sample_name, channel, metric) in enumerate(peak_column_order):
                    excel_col = col_idx + 1
                    base_color = export_colors.get(sample_name, (180, 180, 180))

                    if sample_name not in sample_header_formats:
                        sample_header_formats[sample_name] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(base_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })

                    style_factors = channel_style_factors.get(channel, channel_style_factors['CH1'])

                    if (sample_name, channel) not in channel_header_formats:
                        channel_color = _lighten_color(base_color, style_factors['channel'])
                        channel_header_formats[(sample_name, channel)] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(channel_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        metric_color = _lighten_color(base_color, style_factors['metric'])
                        metric_header_formats[(sample_name, channel)] = workbook.add_format({
                            'bold': True,
                            'bg_color': _rgb_to_hex(metric_color),
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        data_color = _lighten_color(base_color, style_factors['data'])
                        channel_data_formats[(sample_name, channel)] = workbook.add_format({
                            'align': 'center',
                            'bg_color': _rgb_to_hex(data_color),
                            'border': 1
                        })

                    worksheet.write(0, excel_col, sample_name, sample_header_formats[sample_name])
                    worksheet.write(1, excel_col, channel, channel_header_formats[(sample_name, channel)])
                    worksheet.write(2, excel_col, metric.capitalize(), metric_header_formats[(sample_name, channel)])
                    worksheet.set_column(excel_col, excel_col, 14, channel_data_formats[(sample_name, channel)])

state = AnalyticsState()


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
    
    state.suppress_checkbox_callback = True
    try:
        for f in AVAILABLE_FILES:
            rel_path = str(f.relative_to(SAMPLE_DIR)).replace("\\", "/")
            tag = f"sample_chk_{hashlib.md5(rel_path.encode()).hexdigest()}"
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, False)
    finally:
        state.suppress_checkbox_callback = False
    
    update_all_plots()


def export_to_excel_callback():
    """Export data sample aktif ke file Excel"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = EXPORT_DIR / f"radar_samples_{timestamp}.xlsx"
    try:
        state.export_active_to_excel(filepath)
        dpg.set_value("export_status_text", f"✅ Exported to {filepath}")
    except ValueError as err:
        dpg.set_value("export_status_text", f"⚠️ {err}")
    except Exception as exc:
        dpg.set_value("export_status_text", f"❌ Export failed: {exc}")


def toggle_export_metric_callback(sender, app_data, user_data):
    """Toggle metric peak untuk ekspor"""
    state.export_peak_fields[user_data] = bool(app_data)
    if not any(state.export_peak_fields.values()):
        dpg.set_value("export_status_text", "⚠️ Tidak ada metric peak terpilih. Hanya statistik yang akan diexport.")
    else:
        dpg.set_value("export_status_text", "")


def toggle_export_channel_callback(sender, app_data, user_data):
    """Toggle channel untuk ekspor"""
    state.export_channels[user_data] = bool(app_data)
    if not any(state.export_channels.values()):
        dpg.set_value("export_status_text", "⚠️ Minimal pilih satu channel untuk ekspor peak.")
    else:
        dpg.set_value("export_status_text", "")


def update_export_freq_range_callback(sender, app_data, user_data):
    """Update rentang frekuensi filter peak"""
    current_min, current_max = state.export_freq_range
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

    state.export_freq_range = (new_min, new_max)
    dpg.set_value("export_status_text", f"ℹ️ Peak diekspor untuk frekuensi {new_min:.0f}-{new_max:.0f} kHz.")


def update_export_peak_count_callback(sender, app_data):
    """Update jumlah peak yang akan diekspor"""
    try:
        value = int(app_data)
    except (TypeError, ValueError):
        value = state.export_peak_count
    if value <= 0:
        value = 100
    state.export_peak_count = value
    state.refresh_active_sample_peaks()
    update_all_plots()
    dpg.set_value("export_status_text", f"ℹ️ Peak export count diset ke {value}.")

def update_layout_split():
    """Update layout split ratio berdasarkan slider value"""
    if not dpg.does_item_exist("layout_slider"):
        return
    
    split_percent = dpg.get_value("layout_slider")
    
    # Get viewport size
    viewport_width = dpg.get_viewport_client_width()
    
    # Calculate widths (accounting for padding and separator)
    available_width = max(viewport_width - 60, 400)
    left_width = int(available_width * split_percent / 100)
    right_width = available_width - left_width
    
    # Update column widths
    if dpg.does_item_exist("left_column"):
        dpg.configure_item("left_column", width=left_width, height=-1)
    if dpg.does_item_exist("right_column"):
        dpg.configure_item("right_column", width=right_width, height=-1)


def layout_slider_callback(sender, app_data, user_data):
    update_layout_split()


def viewport_resize_callback(sender, app_data):
    update_layout_split()


def _build_filtered_tree(filter_text):
    """Bangun struktur tree dari sample files sesuai filter"""
    tree = {}
    normalized_filter = filter_text.lower()
    for file_path in AVAILABLE_FILES:
        rel_parts = file_path.relative_to(SAMPLE_DIR).parts
        rel_str = "/".join(rel_parts)
        if normalized_filter and normalized_filter not in rel_str.lower():
            continue
        node = tree
        for part in rel_parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append(rel_str)
    return tree


def _render_sample_tree(tree, parent, depth=0):
    """Render tree node secara recursive"""
    directories = sorted(k for k in tree.keys() if k != "__files__")
    for directory in directories:
        node_id = dpg.add_tree_node(
            label=directory,
            parent=parent,
            default_open=(depth == 0),
        )
        _render_sample_tree(tree[directory], node_id, depth + 1)
    file_entries = sorted(tree.get("__files__", []))
    for rel_path in file_entries:
        checkbox_tag = f"sample_chk_{hashlib.md5(rel_path.encode()).hexdigest()}"
        is_active = rel_path in state.active_samples
        checkbox_id = dpg.add_checkbox(
            label=rel_path.split("/")[-1],
            parent=parent,
            default_value=is_active,
            callback=sample_checkbox_callback,
            user_data=rel_path,
            tag=checkbox_tag,
        )
        with dpg.tooltip(checkbox_id):
            dpg.add_text(rel_path)


def update_file_tree_ui():
    """Refresh tampilan tree sample sesuai filter"""
    if not dpg.does_item_exist("sample_tree_container"):
        return
    dpg.delete_item("sample_tree_container", children_only=True)
    tree = _build_filtered_tree(state.sample_filter)
    if not tree:
        dpg.add_text("No samples found", parent="sample_tree_container", color=(200, 100, 100))
        return
    _render_sample_tree(tree, "sample_tree_container")


def sample_search_callback(sender, app_data, user_data):
    state.sample_filter = app_data.strip()
    update_file_tree_ui()


def clear_filter_callback():
    state.sample_filter = ""
    if dpg.does_item_exist("sample_search_input"):
        dpg.set_value("sample_search_input", "")
    update_file_tree_ui()


def sample_checkbox_callback(sender, app_data, user_data):
    rel_path = user_data
    if state.suppress_checkbox_callback:
        return
    if app_data:
        if rel_path not in state.active_samples:
            state.load_sample(rel_path)
    else:
        if rel_path in state.active_samples:
            del state.active_samples[rel_path]
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
    
    # Main window - Fullscreen
    with dpg.window(label="Radar LPDP Analytics", tag="main_window", no_close=False):
        
        dpg.add_text("📊 Radar Sample Comparison Tool", color=(100, 200, 255))
        dpg.add_text("Use the sample explorer to enable/disable files for comparison", color=(150, 150, 150))
        dpg.add_separator()
        
        with dpg.collapsing_header(label="📂 Sample Explorer", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    label="Search",
                    tag="sample_search_input",
                    width=260,
                    hint="Filter folder / file",
                    callback=sample_search_callback,
                    user_data=None,
                )
                dpg.add_button(label="Reset", width=70, callback=clear_filter_callback)
                dpg.add_button(label="🗑️ Clear", width=80, callback=clear_all_callback)
            with dpg.child_window(tag="sample_tree_container", height=170, width=-1, border=True):
                dpg.add_text("Loading samples...")
        
        dpg.add_separator()
        
        # Slider untuk mengatur lebar kolom kiri/kanan
        dpg.add_slider_int(
            label="Layout Split (%)",
            default_value=65,
            min_value=30,
            max_value=70,
            tag="layout_slider",
            width=320,
            callback=layout_slider_callback
        )
        dpg.add_text("← Adjust to resize plot vs table area →", color=(150, 150, 150))
        
        dpg.add_separator()
        
        # Layout: 2 columns dengan responsive width
        with dpg.group(horizontal=True, tag="main_layout_group"):
            
            # Left column: FFT Plots
            with dpg.child_window(tag="left_column", border=False):
                dpg.add_text("FFT Spectrum Comparison", color=(100, 200, 255))
                dpg.add_text("Multiple samples can be overlayed for comparison", color=(150, 150, 150))
                dpg.add_spacer(height=6)
                dpg.add_text("Channel 1 (CH1)", color=(255, 150, 100))
                with dpg.plot(label="CH1 FFT Comparison", height=360, width=-1, tag="ch1_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="fft_ch1_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="fft_ch1_yaxis")
                dpg.add_spacer(height=12)
                dpg.add_text("Channel 2 (CH2)", color=(255, 200, 100))
                with dpg.plot(label="CH2 FFT Comparison", height=360, width=-1, tag="ch2_plot"):
                    dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", tag="fft_ch2_xaxis")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)", tag="fft_ch2_yaxis")

            
            # Right column: Peak Tables & Controls (scrollable)
            with dpg.child_window(tag="right_column", border=False):
                dpg.add_text("Controls & Peak Analysis", color=(100, 255, 150))
                dpg.add_spacer(height=5)
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
                        width=-1
                    )
                    dpg.add_text("💡 Lower value = more aggressive noise removal", color=(150, 150, 150))
                dpg.add_separator()
                dpg.add_spacer(height=5)
                dpg.add_text("CH1 Top Peaks", color=(255, 150, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="ch1_peak_table",
                    height=310,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Sample", width_fixed=True, init_width_or_weight=80)
                    dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=30)
                    dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=50)
                    dpg.add_table_column(label="Freq (kHz)", width_fixed=True, init_width_or_weight=75)
                    dpg.add_table_column(label="Mag (dB)", width_fixed=True, init_width_or_weight=70)
                dpg.add_spacer(height=12)
                dpg.add_text("CH2 Top Peaks", color=(255, 200, 100))
                with dpg.table(
                    header_row=True,
                    borders_innerH=True,
                    borders_outerH=True,
                    borders_innerV=True,
                    borders_outerV=True,
                    tag="ch2_peak_table",
                    height=310,
                    scrollY=True
                ):
                    dpg.add_table_column(label="Sample", width_fixed=True, init_width_or_weight=80)
                    dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=30)
                    dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=50)
                    dpg.add_table_column(label="Freq (kHz)", width_fixed=True, init_width_or_weight=75)
                    dpg.add_table_column(label="Mag (dB)", width_fixed=True, init_width_or_weight=70)

                dpg.add_separator()
                with dpg.collapsing_header(label="📤 Export Options", default_open=True):
                    with dpg.group(horizontal=True):
                        dpg.add_text("Peak fields:", color=(180, 180, 180))
                        dpg.add_checkbox(
                            label="Index",
                            default_value=state.export_peak_fields['index'],
                            callback=toggle_export_metric_callback,
                            user_data="index"
                        )
                        dpg.add_checkbox(
                            label="Freq",
                            default_value=state.export_peak_fields['freq'],
                            callback=toggle_export_metric_callback,
                            user_data="freq"
                        )
                        dpg.add_checkbox(
                            label="Mag",
                            default_value=state.export_peak_fields['mag'],
                            callback=toggle_export_metric_callback,
                            user_data="mag"
                        )
                        dpg.add_spacer(width=10)
                        dpg.add_text("Channels:", color=(180, 180, 180))
                        dpg.add_checkbox(
                            label="CH1",
                            default_value=state.export_channels['ch1'],
                            callback=toggle_export_channel_callback,
                            user_data="ch1"
                        )
                        dpg.add_checkbox(
                            label="CH2",
                            default_value=state.export_channels['ch2'],
                            callback=toggle_export_channel_callback,
                            user_data="ch2"
                        )
                    with dpg.group(horizontal=True):
                        dpg.add_text("Freq (kHz):", color=(180, 180, 180))
                        dpg.add_input_float(
                            label="Min",
                            width=80,
                            default_value=state.export_freq_range[0],
                            format="%.0f",
                            callback=update_export_freq_range_callback,
                            user_data="min"
                        )
                        dpg.add_input_float(
                            label="Max",
                            width=80,
                            default_value=state.export_freq_range[1],
                            format="%.0f",
                            callback=update_export_freq_range_callback,
                            user_data="max"
                        )
                        dpg.add_input_int(
                            label="Peak count",
                            width=90,
                            min_value=1,
                            default_value=state.export_peak_count,
                            callback=update_export_peak_count_callback,
                            step=5
                        )
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="💾 Export to Excel", callback=export_to_excel_callback)
                        dpg.add_spacer(width=10)
                        dpg.add_text("", tag="export_status_text", color=(180, 180, 180))

        dpg.add_separator()
        dpg.add_text("💡 Tip: Use the search box to quickly locate samples across nested folders",
                     color=(150, 150, 150))

    
    # Setup viewport - Fullscreen
    dpg.create_viewport(title="Radar LPDP Analytics - Sample Comparison", width=1920, height=1080)
    dpg.setup_dearpygui()
    dpg.set_viewport_resize_callback(viewport_resize_callback)
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    
    # Set window to fill viewport
    dpg.configure_item("main_window", width=-1, height=-1)
    update_file_tree_ui()

    print("✅ Analytics panel created!")
    print(f"📁 Found {len(AVAILABLE_FILES)} sample files")
    print("🚀 Click sample buttons to load and compare data")

    # Initial layout split
    update_layout_split()
    
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
