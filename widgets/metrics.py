# widgets/metrics.py

import dearpygui.dearpygui as dpg

def create_metrics_widget(parent, width, height):
    """Membuat widget untuk menampilkan metrik frekuensi."""
    with dpg.group(parent=parent):
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

        # --- Detail Peaks & Valleys ---
        dpg.add_spacer(height=6)
        dpg.add_text("Top Peaks & Valleys (CH1)")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="#")
            dpg.add_table_column(label="Index")
            dpg.add_table_column(label="Freq (kHz)")
            dpg.add_table_column(label="Mag (dB)")
            dpg.add_table_column(label="Type")

            # Buat 5 baris default untuk CH1
            for i in range(5):
                with dpg.table_row():
                    dpg.add_text(f"{i+1}")
                    dpg.add_text("-", tag=f"ch1_ext_{i}_index")
                    dpg.add_text("-", tag=f"ch1_ext_{i}_freq")
                    dpg.add_text("-", tag=f"ch1_ext_{i}_mag")
                    dpg.add_text("-", tag=f"ch1_ext_{i}_type")

        dpg.add_spacer(height=6)
        dpg.add_text("Top Peaks & Valleys (CH2)")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label="#")
            dpg.add_table_column(label="Index")
            dpg.add_table_column(label="Freq (kHz)")
            dpg.add_table_column(label="Mag (dB)")
            dpg.add_table_column(label="Type")

            # Buat 5 baris default untuk CH2
            for i in range(5):
                with dpg.table_row():
                    dpg.add_text(f"{i+1}")
                    dpg.add_text("-", tag=f"ch2_ext_{i}_index")
                    dpg.add_text("-", tag=f"ch2_ext_{i}_freq")
                    dpg.add_text("-", tag=f"ch2_ext_{i}_mag")
                    dpg.add_text("-", tag=f"ch2_ext_{i}_type")
