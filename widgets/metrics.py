# widgets/metrics.py

import dearpygui.dearpygui as dpg

def create_metrics_widget():
    """Membuat widget untuk menampilkan metrik frekuensi."""
    with dpg.group(tag="metrics_group"):
        dpg.add_text("Frequency Metrics")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="Channel")
            dpg.add_table_column(label="Peak Frequency (KHz)")
            dpg.add_table_column(label="Peak Magnitude (dB)")

            # Baris untuk Channel 1 (Ganjil)
            with dpg.table_row():
                dpg.add_text("CH1 (Odd)")
                dpg.add_text("N/A", tag="ch1_peak_freq")
                dpg.add_text("N/A", tag="ch1_peak_mag")

            # Baris untuk Channel 2 (Genap)
            with dpg.table_row():
                dpg.add_text("CH2 (Even)")
                dpg.add_text("N/A", tag="ch2_peak_freq")
                dpg.add_text("N/A", tag="ch2_peak_mag")
