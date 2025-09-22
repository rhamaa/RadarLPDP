# widgets/file_analyze_popup.py

import dearpygui.dearpygui as dpg
import os
import numpy as np
import time
from config import SAMPLE_RATE

# Global variables untuk popup analysis
_analysis_window_open = False
_selected_file_path = None
_analysis_data = None

def load_log_file_data(filepath):
    """Memuat dan memproses data dari file log biner menggunakan fungsi dari data_processing.py."""
    try:
        # Gunakan utilitas terpusat untuk memuat dan menyiapkan data
        from functions.data_processing import load_file_and_prepare
        return load_file_and_prepare(filepath, SAMPLE_RATE)
    except Exception as e:
        return None, f"Error loading file: {str(e)}"

def compute_file_analysis(data):
    """Menghitung analisis lengkap dari data yang dimuat menggunakan fungsi dari data_processing.py."""
    try:
        if not data:
            return None
        from functions.data_processing import analyze_loaded_data
        return analyze_loaded_data(data['ch1'], data['ch2'], data['sample_rate'],
                                   n_samples=data.get('n_samples'), duration_s=data.get('duration'))
    except Exception as e:
        print(f"Error in compute_file_analysis: {e}")
        import traceback
        traceback.print_exc()
        return None

def open_file_analysis():
    """Membuka popup window untuk analisis file yang dipilih."""
    global _analysis_window_open, _selected_file_path, _analysis_data
    
    try:
        # Force close any existing popup first
        if _analysis_window_open:
            close_analysis_popup()
            time.sleep(0.1)  # Small delay to ensure cleanup
        
        selected_file = dpg.get_value("log_file_list")
        if not selected_file or selected_file.startswith("Log directory") or selected_file.startswith("No log") or selected_file.startswith("Error"):
            dpg.set_value("file_status_text", "Pilih file log yang valid terlebih dahulu!")
            return
        
        _selected_file_path = os.path.join("log", selected_file)
        
        # Load and analyze data
        dpg.set_value("file_status_text", f"Memuat file: {selected_file}...")
        data, error = load_log_file_data(_selected_file_path)
        
        if error:
            dpg.set_value("file_status_text", f"Error: {error}")
            return
        
        _analysis_data = compute_file_analysis(data)
        if not _analysis_data:
            dpg.set_value("file_status_text", "Gagal menganalisis data")
            return
        
        # Create analysis popup window
        _analysis_window_open = True
        create_analysis_popup(data, _analysis_data, selected_file)
        dpg.set_value("file_status_text", f"Analisis selesai untuk: {selected_file}")
        
    except Exception as e:
        dpg.set_value("file_status_text", f"Error saat analisis: {str(e)}")
        print(f"Error in open_file_analysis: {e}")
        import traceback
        traceback.print_exc()

def create_analysis_popup(raw_data, analysis_data, filename):
    """Membuat window popup untuk analisis data gelombang."""
    with dpg.window(label=f"Waveform Analysis - {filename}", 
                   width=1200, height=800, 
                   modal=True, tag="analysis_popup"):
        
        # File info section
        with dpg.group():
            dpg.add_text(f"File: {filename}")
            dpg.add_text(f"Duration: {raw_data['duration']:.3f} seconds")
            dpg.add_text(f"Samples: {raw_data['n_samples']:,}")
            dpg.add_text(f"Sample Rate: {raw_data['sample_rate']:,} Hz")
            dpg.add_separator()
        
        # Create tabs for different analysis views
        with dpg.tab_bar():
            # Time Domain Tab
            with dpg.tab(label="Time Domain"):
                create_time_domain_tab(raw_data)
            
            # Frequency Domain Tab
            with dpg.tab(label="Frequency Domain"):
                create_frequency_domain_tab(analysis_data)
            
            # Statistics Tab
            with dpg.tab(label="Statistics"):
                create_statistics_tab(analysis_data)
            
            # Peak Analysis Tab
            with dpg.tab(label="Peak Analysis"):
                create_peak_analysis_tab(analysis_data)
            
            # File Management Tab
            with dpg.tab(label="File Management"):
                create_file_management_tab(filename)
        
        # Close button
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(label="Close", callback=close_analysis_popup, width=100)
            dpg.add_button(label="Export Data", callback=lambda: export_analysis_data(filename, analysis_data), width=120)

def create_time_domain_tab(raw_data):
    """Membuat tab untuk analisis domain waktu."""
    with dpg.group():
        dpg.add_text("Time Domain Analysis")
        
        # Ensure arrays are C-contiguous
        ch1_data = np.ascontiguousarray(raw_data['ch1'], dtype=np.float64)
        ch2_data = np.ascontiguousarray(raw_data['ch2'], dtype=np.float64)

        # Use channel indices as x-axis (requested):
        ch1_idx = np.ascontiguousarray(np.arange(len(ch1_data)), dtype=np.float64)
        ch2_idx = np.ascontiguousarray(np.arange(len(ch2_data)), dtype=np.float64)
        
        # Time domain plots
        with dpg.plot(label="Channel 1 - Time Domain", height=200, width=-1):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Index")
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Amplitude")
            dpg.add_line_series(ch1_idx, ch1_data, label="CH1 (odd)", parent=y_axis)
        
        with dpg.plot(label="Channel 2 - Time Domain", height=200, width=-1):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Index")
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Amplitude")
            dpg.add_line_series(ch2_idx, ch2_data, label="CH2 (even)", parent=y_axis)

        # Raw samples table (show channel index and original interleaved index)
        dpg.add_separator()
        dpg.add_text("Raw Samples (first 50) — CH1 assumed odd original index, CH2 even")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True,
                       borders_innerV=True, borders_outerV=True, resizable=True,
                       policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(label="CH1 Idx")
            dpg.add_table_column(label="CH1 OrigIdx (odd)")
            dpg.add_table_column(label="CH1 Value")
            dpg.add_table_column(label="CH2 Idx")
            dpg.add_table_column(label="CH2 OrigIdx (even)")
            dpg.add_table_column(label="CH2 Value")

            max_rows = int(min(50, len(ch1_data), len(ch2_data)))
            for i in range(max_rows):
                ch1_val = float(ch1_data[i])
                ch2_val = float(ch2_data[i])
                # Original interleaved indices assumption: CH1=2*i+1 (odd), CH2=2*i (even)
                ch1_orig = 2 * i + 1
                ch2_orig = 2 * i
                with dpg.table_row():
                    dpg.add_text(str(i))
                    dpg.add_text(str(ch1_orig))
                    dpg.add_text(f"{ch1_val:.6f}")
                    dpg.add_text(str(i))
                    dpg.add_text(str(ch2_orig))
                    dpg.add_text(f"{ch2_val:.6f}")

def create_frequency_domain_tab(analysis_data):
    """Membuat tab untuk analisis domain frekuensi."""
    with dpg.group():
        dpg.add_text("Frequency Domain Analysis")
        
        # FFT plots
        ch1_fft = analysis_data['ch1_fft']
        ch2_fft = analysis_data['ch2_fft']
        
        # Ensure arrays are C-contiguous
        ch1_freqs = np.ascontiguousarray(ch1_fft['frequencies'], dtype=np.float64)
        ch1_mags = np.ascontiguousarray(ch1_fft['magnitudes'], dtype=np.float64)
        ch2_freqs = np.ascontiguousarray(ch2_fft['frequencies'], dtype=np.float64)
        ch2_mags = np.ascontiguousarray(ch2_fft['magnitudes'], dtype=np.float64)
        
        with dpg.plot(label="Channel 1 - FFT Spectrum", height=200, width=-1):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", log_scale=True)
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)")
            dpg.add_line_series(ch1_freqs, ch1_mags, 
                              label="CH1 FFT", parent=y_axis)
        
        with dpg.plot(label="Channel 2 - FFT Spectrum", height=200, width=-1):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (kHz)", log_scale=True)
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Magnitude (dB)")
            dpg.add_line_series(ch2_freqs, ch2_mags, 
                              label="CH2 FFT", parent=y_axis)

def create_statistics_tab(analysis_data):
    """Membuat tab untuk statistik data."""
    with dpg.group():
        dpg.add_text("Statistical Analysis")
        
        # Channel 1 Statistics
        dpg.add_text("Channel 1 Statistics:")
        ch1_stats = analysis_data['ch1_stats']
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                      borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Metric")
            dpg.add_table_column(label="Value")
            
            with dpg.table_row():
                dpg.add_text("Mean")
                dpg.add_text(f"{ch1_stats['mean']:.6f}")
            with dpg.table_row():
                dpg.add_text("Standard Deviation")
                dpg.add_text(f"{ch1_stats['std']:.6f}")
            with dpg.table_row():
                dpg.add_text("Minimum")
                dpg.add_text(f"{ch1_stats['min']:.6f}")
            with dpg.table_row():
                dpg.add_text("Maximum")
                dpg.add_text(f"{ch1_stats['max']:.6f}")
            with dpg.table_row():
                dpg.add_text("RMS")
                dpg.add_text(f"{ch1_stats['rms']:.6f}")
        
        dpg.add_separator()
        
        # Channel 2 Statistics
        dpg.add_text("Channel 2 Statistics:")
        ch2_stats = analysis_data['ch2_stats']
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                      borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Metric")
            dpg.add_table_column(label="Value")
            
            with dpg.table_row():
                dpg.add_text("Mean")
                dpg.add_text(f"{ch2_stats['mean']:.6f}")
            with dpg.table_row():
                dpg.add_text("Standard Deviation")
                dpg.add_text(f"{ch2_stats['std']:.6f}")
            with dpg.table_row():
                dpg.add_text("Minimum")
                dpg.add_text(f"{ch2_stats['min']:.6f}")
            with dpg.table_row():
                dpg.add_text("Maximum")
                dpg.add_text(f"{ch2_stats['max']:.6f}")
            with dpg.table_row():
                dpg.add_text("RMS")
                dpg.add_text(f"{ch2_stats['rms']:.6f}")

def create_peak_analysis_tab(analysis_data):
    """Membuat tab untuk analisis puncak frekuensi."""
    with dpg.group():
        dpg.add_text("Peak Frequency Analysis")
        
        # Channel 1 Peaks
        dpg.add_text("Channel 1 - Top Peaks:")
        ch1_fft = analysis_data['ch1_fft']
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                      borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Rank")
            dpg.add_table_column(label="Index")
            dpg.add_table_column(label="Frequency (kHz)")
            dpg.add_table_column(label="Magnitude (dB)")
            
            for i, (idx, freq, mag) in enumerate(zip(
                ch1_fft.get('peak_indices', []),
                ch1_fft['peak_frequencies'],
                ch1_fft['peak_magnitudes']
            )):
                with dpg.table_row():
                    dpg.add_text(f"{i+1}")
                    dpg.add_text(str(int(idx)))
                    dpg.add_text(f"{float(freq):.2f}")
                    dpg.add_text(f"{float(mag):.2f}")
        
        dpg.add_separator()
        
        # Channel 2 Peaks
        dpg.add_text("Channel 2 - Top Peaks:")
        ch2_fft = analysis_data['ch2_fft']
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                      borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Rank")
            dpg.add_table_column(label="Index")
            dpg.add_table_column(label="Frequency (kHz)")
            dpg.add_table_column(label="Magnitude (dB)")
            
            for i, (idx, freq, mag) in enumerate(zip(
                ch2_fft.get('peak_indices', []),
                ch2_fft['peak_frequencies'],
                ch2_fft['peak_magnitudes']
            )):
                with dpg.table_row():
                    dpg.add_text(f"{i+1}")
                    dpg.add_text(str(int(idx)))
                    dpg.add_text(f"{float(freq):.2f}")
                    dpg.add_text(f"{float(mag):.2f}")

def create_file_management_tab(filename):
    """Membuat tab untuk manajemen file dengan fitur rename."""
    with dpg.group():
        dpg.add_text("File Management")
        
        # Current file info
        dpg.add_text(f"Current File: {filename}")
        
        # File rename section
        dpg.add_separator()
        dpg.add_text("Rename File")
        
        with dpg.group(horizontal=True):
            dpg.add_input_text(label="New Name", default_value=filename, tag="rename_input", width=300)
            dpg.add_button(label="Rename", callback=lambda: rename_file(filename), width=80)
        
        dpg.add_text("", tag="rename_status")
        
        # File operations
        dpg.add_separator()
        dpg.add_text("File Operations")
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="Delete File", callback=lambda: delete_file(filename), width=100)
            dpg.add_button(label="Copy File", callback=lambda: copy_file(filename), width=100)
        
        dpg.add_text("", tag="operation_status")

def rename_file(old_filename):
    """Mengganti nama file."""
    try:
        new_name = dpg.get_value("rename_input")
        if not new_name or new_name == old_filename:
            dpg.set_value("rename_status", "Nama file tidak berubah")
            return
        
        # Validate new name
        if not new_name.endswith('.bin'):
            new_name += '.bin'
        
        old_path = os.path.join("log", old_filename)
        new_path = os.path.join("log", new_name)
        
        if os.path.exists(new_path):
            dpg.set_value("rename_status", f"File '{new_name}' sudah ada!")
            return
        
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            dpg.set_value("rename_status", f"File berhasil diubah dari '{old_filename}' ke '{new_name}'")
            
            # Update the listbox
            from widgets.file import refresh_log_files
            refresh_log_files()
            
            # Update the popup title
            dpg.set_item_label("analysis_popup", f"Waveform Analysis - {new_name}")
            
        else:
            dpg.set_value("rename_status", f"File '{old_filename}' tidak ditemukan!")
            
    except Exception as e:
        dpg.set_value("rename_status", f"Error saat rename: {str(e)}")

def delete_file(filename):
    """Menghapus file."""
    try:
        file_path = os.path.join("log", filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            dpg.set_value("operation_status", f"File '{filename}' berhasil dihapus")
            
            # Update the listbox
            from widgets.file import refresh_log_files
            refresh_log_files()
            
            # Close popup since file is deleted
            close_analysis_popup()
            
        else:
            dpg.set_value("operation_status", f"File '{filename}' tidak ditemukan!")
            
    except Exception as e:
        dpg.set_value("operation_status", f"Error saat hapus: {str(e)}")

def copy_file(filename):
    """Membuat salinan file."""
    try:
        import shutil
        from datetime import datetime
        
        old_path = os.path.join("log", filename)
        
        if os.path.exists(old_path):
            # Create new filename with timestamp
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{name}_copy_{timestamp}{ext}"
            new_path = os.path.join("log", new_filename)
            
            shutil.copy2(old_path, new_path)
            dpg.set_value("operation_status", f"File berhasil disalin sebagai '{new_filename}'")
            
            # Update the listbox
            from widgets.file import refresh_log_files
            refresh_log_files()
            
        else:
            dpg.set_value("operation_status", f"File '{filename}' tidak ditemukan!")
            
    except Exception as e:
        dpg.set_value("operation_status", f"Error saat copy: {str(e)}")

def close_analysis_popup():
    """Menutup popup analisis dengan cleanup yang lebih robust."""
    global _analysis_window_open
    try:
        # Force cleanup
        if dpg.does_item_exist("analysis_popup"):
            dpg.delete_item("analysis_popup")
        
        # Reset global state
        _analysis_window_open = False
        _selected_file_path = None
        _analysis_data = None
        
        print("Analysis popup closed and cleaned up successfully")
        
    except Exception as e:
        print(f"Error closing popup: {e}")
        # Force reset even if there's an error
        _analysis_window_open = False
        _selected_file_path = None
        _analysis_data = None

def export_analysis_data(filename, analysis_data):
    """Export data analisis ke file teks."""
    try:
        export_filename = f"analysis_{filename}_{int(time.time())}.txt"
        export_path = os.path.join("log", export_filename)
        
        with open(export_path, 'w') as f:
            f.write(f"Waveform Analysis Report\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source File: {filename}\n")
            f.write("="*50 + "\n\n")
            
            # File info
            file_info = analysis_data['file_info']
            f.write("File Information:\n")
            f.write(f"  Duration: {file_info['duration']:.3f} seconds\n")
            f.write(f"  Samples: {file_info['n_samples']:,}\n")
            f.write(f"  Sample Rate: {file_info['sample_rate']:,} Hz\n\n")
            
            # Channel 1 Statistics
            ch1_stats = analysis_data['ch1_stats']
            f.write("Channel 1 Statistics:\n")
            f.write(f"  Mean: {ch1_stats['mean']:.6f}\n")
            f.write(f"  Std Dev: {ch1_stats['std']:.6f}\n")
            f.write(f"  Min: {ch1_stats['min']:.6f}\n")
            f.write(f"  Max: {ch1_stats['max']:.6f}\n")
            f.write(f"  RMS: {ch1_stats['rms']:.6f}\n\n")
            
            # Channel 2 Statistics
            ch2_stats = analysis_data['ch2_stats']
            f.write("Channel 2 Statistics:\n")
            f.write(f"  Mean: {ch2_stats['mean']:.6f}\n")
            f.write(f"  Std Dev: {ch2_stats['std']:.6f}\n")
            f.write(f"  Min: {ch2_stats['min']:.6f}\n")
            f.write(f"  Max: {ch2_stats['max']:.6f}\n")
            f.write(f"  RMS: {ch2_stats['rms']:.6f}\n\n")
            
            # Peak Analysis
            ch1_fft = analysis_data['ch1_fft']
            f.write("Channel 1 Peak Frequencies:\n")
            for i, (freq, mag) in enumerate(zip(ch1_fft['peak_frequencies'], ch1_fft['peak_magnitudes'])):
                f.write(f"  {i+1}. {freq:.2f} kHz, {mag:.2f} dB\n")
            
            f.write("\nChannel 2 Peak Frequencies:\n")
            ch2_fft = analysis_data['ch2_fft']
            for i, (freq, mag) in enumerate(zip(ch2_fft['peak_frequencies'], ch2_fft['peak_magnitudes'])):
                f.write(f"  {i+1}. {freq:.2f} kHz, {mag:.2f} dB\n")
        
        dpg.set_value("file_status_text", f"Data exported to: {export_filename}")
        
    except Exception as e:
        dpg.set_value("file_status_text", f"Export error: {str(e)}")
