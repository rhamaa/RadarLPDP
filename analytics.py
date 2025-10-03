#!/usr/bin/env python3
"""
RF Analytics Dashboard
======================
Dashboard analitik untuk data akuisisi RF dari ADC PCI-9846H
Author: Raihan Muhammad
Version: 1.0

Data Format:
- Sample Rate: 20 MHz
- Channels: CH1 & CH3 (interleaved)
- Buffer: 8192 samples per acquisition
- File Format: [CH1_0, CH3_0, CH1_1, CH3_1, ...]
"""

import datetime
import os
from pathlib import Path
from typing import Dict, Tuple, Any, Optional

import holoviews as hv
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import panel as pn
import param
from holoviews import opts
from scipy import signal
from scipy.fft import fft, fftfreq, rfft, rfftfreq
from sklearn.cluster import DBSCAN

from functions.data_processing import (
    load_and_process_data,
    compute_fft,
    find_peak_metrics,
)

# Enable Panel extensions
pn.extension('tabulator')
hv.extension('bokeh')

# Set matplotlib style for better-looking plots
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams.update({
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 14,
    'lines.linewidth': 1.2,
    'grid.alpha': 0.3
})

# === KONFIGURASI SISTEM ===
SAMPLE_RATE = 20_000_000  # 20 MHz
BUFFER_SAMPLES = 8192
CHANNELS = ['CH1', 'CH3']
LIVE_FILE = 'live/live_acquisition_ui.bin'

class RFAnalytics(param.Parameterized):
    """
    Main RF Analytics Dashboard Class
    """
    
    # Parameters untuk kontrol UI
    auto_refresh = param.Boolean(default=True, doc="Auto refresh dari file live")
    refresh_rate = param.Number(default=1.0, bounds=(0.1, 10.0), doc="Refresh rate (detik)")
    window_function = param.Selector(
        default='hann', 
        objects=['hann', 'hamming', 'blackman', 'bartlett', 'none'],
        doc="Window function untuk FFT"
    )
    fft_size = param.Integer(default=8192, bounds=(1024, 32768), doc="FFT Size")
    freq_range_low = param.Number(default=0, bounds=(0, 10_000_000), doc="Freq Range Low (Hz)")
    freq_range_high = param.Number(default=10_000_000, bounds=(0, 10_000_000), doc="Freq Range High (Hz)")
    
    def __init__(self, **params):
        super().__init__(**params)
        self.data_ch1 = np.array([])
        self.data_ch2 = np.array([])
        self.time_axis = np.array([])
        self.freq_axis = np.array([])
        self.last_update = datetime.datetime.now()
        
    def load_binary_data(self, filepath: str) -> Tuple[np.ndarray, np.ndarray, bool]:
        """Load and parse binary data from acquisition file.
        
        Uses shared data loading function from data_processing module.
        Converts raw ADC values to voltage.
        
        Args:
            filepath: Path to binary data file
            
        Returns:
            Tuple of (ch1_voltage, ch2_voltage, success)
        """
        ch1_data, ch2_data, n_samples, _ = load_and_process_data(filepath, SAMPLE_RATE)
        
        if ch1_data is None or n_samples is None or n_samples <= 0:
            return np.array([]), np.array([]), False
        
        # Convert to voltage (PCI-9846H: ±10V range, 16-bit resolution)
        # Note: data_processing already removes DC offset, so we add back the offset
        # before voltage conversion for accurate representation
        ch1_voltage = ch1_data.astype(np.float64) * (20.0 / 65536)
        ch2_voltage = ch2_data.astype(np.float64) * (20.0 / 65536)
        
        return ch1_voltage, ch2_voltage, True
    
    def compute_time_domain_metrics(self, data: np.ndarray) -> Dict[str, float]:
        """Compute time domain statistics.
        
        Args:
            data: Input signal data
            
        Returns:
            Dictionary containing RMS, peak, mean, std, p2p, and crest factor
        """
        if len(data) == 0:
            return {}
        
        rms = np.sqrt(np.mean(data**2))
        peak = np.max(np.abs(data))
        
        return {
            'rms': rms,
            'peak': peak,
            'mean': np.mean(data),
            'std': np.std(data),
            'p2p': np.ptp(data),
            'crest_factor': peak / rms if rms > 0 else 0
        }
    
    def compute_frequency_domain(
        self,
        data: np.ndarray,
        window_func: str = 'hanning'
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Compute FFT and frequency domain metrics.
        
        Args:
            data: Input signal data
            window_func: Window function name
            
        Returns:
            Tuple of (metrics_dict, frequencies, magnitude_db)
        """
        if len(data) == 0:
            return {}, np.array([]), np.array([])
        
        # Use shared FFT computation (returns kHz, we need Hz)
        freqs_khz, magnitude_db = compute_fft(
            data.astype(np.float32),
            SAMPLE_RATE,
            window=window_func if window_func != 'none' else ''
        )
        freqs = freqs_khz * 1000  # Convert kHz to Hz
        
        # Compute FFT for spectral centroid calculation
        fft_data = rfft(data, n=self.fft_size)
        
        # Find peaks
        peaks, _ = signal.find_peaks(magnitude_db, height=-60, distance=10)
        
        # Get peak frequency and magnitude
        peak_freq, peak_mag = find_peak_metrics(freqs_khz, magnitude_db)
        
        # Frequency domain metrics
        metrics = {
            'peak_freq': peak_freq * 1000,  # Convert kHz to Hz
            'peak_magnitude': peak_mag,
            'bandwidth_3db': self._compute_3db_bandwidth(freqs, magnitude_db),
            'spectral_centroid': np.sum(freqs * np.abs(fft_data)) / np.sum(np.abs(fft_data)),
            'num_peaks': len(peaks),
            'snr_estimate': self._estimate_snr(magnitude_db)
        }
        
        return metrics, freqs, magnitude_db
    
    def _compute_3db_bandwidth(
        self,
        freqs: np.ndarray,
        magnitude_db: np.ndarray
    ) -> float:
        """Compute 3dB bandwidth.
        
        Args:
            freqs: Frequency array
            magnitude_db: Magnitude spectrum in dB
            
        Returns:
            3dB bandwidth in Hz
        """
        if len(magnitude_db) == 0:
            return 0.0
            
        max_mag = np.max(magnitude_db)
        indices_3db = np.where(magnitude_db >= max_mag - 3)[0]
        
        if len(indices_3db) > 1:
            return float(freqs[indices_3db[-1]] - freqs[indices_3db[0]])
        return 0.0
    
    def _estimate_snr(self, magnitude_db: np.ndarray) -> float:
        """Estimate SNR using simple method.
        
        Args:
            magnitude_db: Magnitude spectrum in dB
            
        Returns:
            Estimated SNR in dB
        """
        if len(magnitude_db) == 0:
            return 0.0
            
        signal_power = np.max(magnitude_db)
        noise_floor = np.median(magnitude_db)
        return float(signal_power - noise_floor)
    
    def create_time_domain_plot(self) -> pn.pane.Markdown | pn.pane.Matplotlib:
        """Create time domain visualization.
        
        Returns:
            Panel pane containing the plot or error message
        """
        if len(self.data_ch1) == 0:
            return pn.pane.Markdown(
                "## ⚠️ No data available",
                styles={'text-align': 'center', 'color': '#ff6b6b'}
            )
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        fig.patch.set_facecolor('#f8f9fa')
        
        time_us = self.time_axis * 1e6  # Convert to microseconds
        
        # CH1 plot with enhanced styling
        ax1.plot(time_us, self.data_ch1, color='#4287f5', linewidth=1.5, 
                label='CH1 Signal', alpha=0.8)
        ax1.fill_between(time_us, self.data_ch1, alpha=0.2, color='#4287f5')
        ax1.set_ylabel('Amplitude (V)', fontweight='bold')
        ax1.set_title('Channel 1 - Time Domain Analysis', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.4, linestyle='--')
        ax1.legend(loc='upper right', framealpha=0.9)
        ax1.set_facecolor('#fafafa')
        
        # CH2 plot with enhanced styling
        ax2.plot(time_us, self.data_ch2, color='#ff6b6b', linewidth=1.5, 
                label='CH3 Signal', alpha=0.8)
        ax2.fill_between(time_us, self.data_ch2, alpha=0.2, color='#ff6b6b')
        ax2.set_xlabel('Time (μs)', fontweight='bold')
        ax2.set_ylabel('Amplitude (V)', fontweight='bold')
        ax2.set_title('Channel 3 - Time Domain Analysis', fontsize=14, fontweight='bold', pad=20)
        ax2.grid(True, alpha=0.4, linestyle='--')
        ax2.legend(loc='upper right', framealpha=0.9)
        ax2.set_facecolor('#fafafa')
        
        plt.tight_layout(pad=3.0)
        return pn.pane.Matplotlib(fig, sizing_mode='stretch_both')
    
    def create_frequency_domain_plot(self) -> pn.pane.Markdown | pn.pane.Matplotlib:
        """Create frequency domain visualization.
        
        Returns:
            Panel pane containing the FFT plot or error message
        """
        if len(self.data_ch1) == 0:
            return pn.pane.Markdown(
                "## ⚠️ No data available",
                styles={'text-align': 'center', 'color': '#ff6b6b'}
            )
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        fig.patch.set_facecolor('#f8f9fa')
        
        # Compute FFT for both channels
        _, freqs_ch1, mag_ch1 = self.compute_frequency_domain(self.data_ch1, self.window_function)
        _, freqs_ch2, mag_ch2 = self.compute_frequency_domain(self.data_ch2, self.window_function)
        
        # Apply frequency range filter
        freq_mask_ch1 = (freqs_ch1 >= self.freq_range_low) & (freqs_ch1 <= self.freq_range_high)
        freq_mask_ch2 = (freqs_ch2 >= self.freq_range_low) & (freqs_ch2 <= self.freq_range_high)
        
        # CH1 FFT with gradient colors
        ax1.plot(freqs_ch1[freq_mask_ch1]/1e6, mag_ch1[freq_mask_ch1], 
                color='#4287f5', linewidth=2, alpha=0.9, label=f'CH1 ({self.window_function} window)')
        ax1.fill_between(freqs_ch1[freq_mask_ch1]/1e6, mag_ch1[freq_mask_ch1], 
                        alpha=0.3, color='#4287f5')
        ax1.set_ylabel('Magnitude (dB)', fontweight='bold')
        ax1.set_title('Channel 1 - Frequency Domain Analysis', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.4, linestyle='--')
        ax1.legend(loc='upper right', framealpha=0.9)
        ax1.set_facecolor('#fafafa')
        
        # CH2 FFT with gradient colors
        ax2.plot(freqs_ch2[freq_mask_ch2]/1e6, mag_ch2[freq_mask_ch2], 
                color='#ff6b6b', linewidth=2, alpha=0.9, label=f'CH3 ({self.window_function} window)')
        ax2.fill_between(freqs_ch2[freq_mask_ch2]/1e6, mag_ch2[freq_mask_ch2], 
                        alpha=0.3, color='#ff6b6b')
        ax2.set_xlabel('Frequency (MHz)', fontweight='bold')
        ax2.set_ylabel('Magnitude (dB)', fontweight='bold')
        ax2.set_title('Channel 3 - Frequency Domain Analysis', fontsize=14, fontweight='bold', pad=20)
        ax2.grid(True, alpha=0.4, linestyle='--')
        ax2.legend(loc='upper right', framealpha=0.9)
        ax2.set_facecolor('#fafafa')
        
        plt.tight_layout(pad=3.0)
        return pn.pane.Matplotlib(fig, sizing_mode='stretch_both')
    
    def create_metrics_table(self):
        """Create metrics summary table"""
        if len(self.data_ch1) == 0:
            return pn.pane.Markdown("## No data available")
            
        # Time domain metrics
        ch1_time_metrics = self.compute_time_domain_metrics(self.data_ch1)
        ch2_time_metrics = self.compute_time_domain_metrics(self.data_ch2)
        
        # Frequency domain metrics
        ch1_freq_metrics, _, _ = self.compute_frequency_domain(self.data_ch1, self.window_function)
        ch2_freq_metrics, _, _ = self.compute_frequency_domain(self.data_ch2, self.window_function)
        
        # Create DataFrame
        metrics_data = {
            'Metric': [
                'RMS (V)', 'Peak (V)', 'Mean (V)', 'Std Dev (V)', 'Peak-to-Peak (V)', 'Crest Factor',
                'Peak Freq (MHz)', 'Peak Magnitude (dB)', '3dB BW (MHz)', 
                'Spectral Centroid (MHz)', 'Num Peaks', 'SNR Estimate (dB)'
            ],
            'CH1': [
                f"{ch1_time_metrics.get('rms', 0):.4f}",
                f"{ch1_time_metrics.get('peak', 0):.4f}",
                f"{ch1_time_metrics.get('mean', 0):.4f}",
                f"{ch1_time_metrics.get('std', 0):.4f}",
                f"{ch1_time_metrics.get('p2p', 0):.4f}",
                f"{ch1_time_metrics.get('crest_factor', 0):.2f}",
                f"{ch1_freq_metrics.get('peak_freq', 0)/1e6:.3f}",
                f"{ch1_freq_metrics.get('peak_magnitude', 0):.1f}",
                f"{ch1_freq_metrics.get('bandwidth_3db', 0)/1e6:.3f}",
                f"{ch1_freq_metrics.get('spectral_centroid', 0)/1e6:.3f}",
                f"{ch1_freq_metrics.get('num_peaks', 0)}",
                f"{ch1_freq_metrics.get('snr_estimate', 0):.1f}"
            ],
            'CH3': [
                f"{ch2_time_metrics.get('rms', 0):.4f}",
                f"{ch2_time_metrics.get('peak', 0):.4f}",
                f"{ch2_time_metrics.get('mean', 0):.4f}",
                f"{ch2_time_metrics.get('std', 0):.4f}",
                f"{ch2_time_metrics.get('p2p', 0):.4f}",
                f"{ch2_time_metrics.get('crest_factor', 0):.2f}",
                f"{ch2_freq_metrics.get('peak_freq', 0)/1e6:.3f}",
                f"{ch2_freq_metrics.get('peak_magnitude', 0):.1f}",
                f"{ch2_freq_metrics.get('bandwidth_3db', 0)/1e6:.3f}",
                f"{ch2_freq_metrics.get('spectral_centroid', 0)/1e6:.3f}",
                f"{ch2_freq_metrics.get('num_peaks', 0)}",
                f"{ch2_freq_metrics.get('snr_estimate', 0):.1f}"
            ]
        }
        
        df = pd.DataFrame(metrics_data)
        
        # Create styled metrics display
        metrics_html = """
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 15px; padding: 25px; margin: 10px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
            <h2 style="color: white; text-align: center; font-family: 'Arial', sans-serif; 
                       margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                📊 Signal Analysis Metrics
            </h2>
            <div style="background: rgba(255,255,255,0.95); border-radius: 10px; padding: 20px;">
                <table style="width: 100%; border-collapse: collapse; font-family: 'Arial', sans-serif;">
                    <thead>
                        <tr style="background: linear-gradient(90deg, #4287f5, #ff6b6b); color: white;">
                            <th style="padding: 12px; text-align: left; border-radius: 8px 0 0 0;">Metric</th>
                            <th style="padding: 12px; text-align: center; color: #4287f5; background: #f0f8ff;">🔵 CH1</th>
                            <th style="padding: 12px; text-align: center; color: #ff6b6b; background: #fff5f5; border-radius: 0 8px 0 0;">🔴 CH3</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for i, (_, row) in enumerate(df.iterrows()):
            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            metrics_html += f"""
                        <tr style="background: {bg_color};">
                            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">{row['Metric']}</td>
                            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6; color: #4287f5; font-weight: bold;">{row['CH1']}</td>
                            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6; color: #ff6b6b; font-weight: bold;">{row['CH3']}</td>
                        </tr>
            """
        
        metrics_html += """
                    </tbody>
                </table>
            </div>
        </div>
        """
        
        return pn.pane.HTML(metrics_html, sizing_mode='stretch_width')
    
    def update_data(self):
        """Update data from live file"""
        ch1, ch2, success = self.load_binary_data(LIVE_FILE)
        
        if success and len(ch1) > 0:
            self.data_ch1 = ch1
            self.data_ch2 = ch2  
            self.time_axis = np.arange(len(ch1)) / SAMPLE_RATE
            self.last_update = datetime.datetime.now()
            return True
        return False
    
    def create_status_panel(self):
        """Create status information panel"""
        status_html = f"""
        <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                    border-radius: 15px; padding: 25px; margin: 10px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
            <h2 style="color: white; text-align: center; font-family: 'Arial', sans-serif; 
                       margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                📡 System Status & Information
            </h2>
            <div style="background: rgba(255,255,255,0.95); border-radius: 10px; padding: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-family: 'Arial', sans-serif;">
                    <div style="background: #f0f8ff; padding: 15px; border-radius: 8px; border-left: 4px solid #4287f5;">
                        <h3 style="color: #4287f5; margin: 0 0 10px 0;">⏰ Timing Information</h3>
                        <p><strong>Last Update:</strong> {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Sample Rate:</strong> {SAMPLE_RATE:,} Hz</p>
                        <p><strong>Duration:</strong> {len(self.data_ch1)/SAMPLE_RATE*1000:.2f} ms</p>
                    </div>
                    <div style="background: #fff5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #ff6b6b;">
                        <h3 style="color: #ff6b6b; margin: 0 0 10px 0;">💾 Data Information</h3>
                        <p><strong>Buffer Size:</strong> {BUFFER_SAMPLES:,} samples</p>
                        <p><strong>CH1 Length:</strong> {len(self.data_ch1):,} samples</p>
                        <p><strong>CH3 Length:</strong> {len(self.data_ch2):,} samples</p>
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #17a2b8;">
                    <h3 style="color: #17a2b8; margin: 0 0 10px 0;">🔧 Configuration</h3>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <p><strong>Window Function:</strong> {self.window_function}</p>
                        <p><strong>FFT Size:</strong> {self.fft_size:,}</p>
                        <p><strong>Auto Refresh:</strong> {'✅ Enabled' if self.auto_refresh else '❌ Disabled'}</p>
                    </div>
                </div>
            </div>
        </div>
        """
        return pn.pane.HTML(status_html, sizing_mode='stretch_width')
    
    # === ADVANCED ANALYTICS METHODS ===
    
    def compute_cross_correlation(self, ch1_data, ch2_data):
        """Compute cross-correlation between channels"""
        if len(ch1_data) != len(ch2_data) or len(ch1_data) == 0:
            return np.array([]), np.array([])
            
        # Normalize data
        ch1_norm = (ch1_data - np.mean(ch1_data)) / np.std(ch1_data)
        ch2_norm = (ch2_data - np.mean(ch2_data)) / np.std(ch2_data)
        
        # Cross-correlation
        correlation = signal.correlate(ch1_norm, ch2_norm, mode='full')
        lags = signal.correlation_lags(len(ch1_data), len(ch2_data), mode='full')
        
        return correlation, lags / SAMPLE_RATE  # Convert to time
    
    def detect_pulses(self, data, threshold_factor=3.0):
        """Detect pulses in signal"""
        if len(data) == 0:
            return []
            
        # Calculate adaptive threshold
        noise_level = np.std(data)
        threshold = threshold_factor * noise_level
        
        # Find peaks above threshold
        peaks, properties = signal.find_peaks(
            np.abs(data), 
            height=threshold,
            distance=int(0.001 * SAMPLE_RATE)  # Minimum 1ms between pulses
        )
        
        pulse_info = []
        for peak in peaks:
            pulse_info.append({
                'time': peak / SAMPLE_RATE,
                'amplitude': data[peak],
                'index': peak
            })
            
        return pulse_info
    
    def compute_phase_difference(self, ch1_data, ch2_data):
        """Compute phase difference between channels"""
        if len(ch1_data) != len(ch2_data) or len(ch1_data) == 0:
            return {}
            
        # FFT both channels
        fft_ch1 = fft(ch1_data)
        fft_ch2 = fft(ch2_data)
        
        # Compute phase difference
        phase_diff = np.angle(fft_ch2) - np.angle(fft_ch1)
        freqs = fftfreq(len(ch1_data), 1/SAMPLE_RATE)
        
        # Find dominant frequency for phase analysis
        magnitude_ch1 = np.abs(fft_ch1)
        dominant_freq_idx = np.argmax(magnitude_ch1[1:len(magnitude_ch1)//2]) + 1
        
        return {
            'phase_diff_spectrum': phase_diff[:len(phase_diff)//2],
            'frequencies': freqs[:len(freqs)//2],
            'dominant_phase_diff': phase_diff[dominant_freq_idx],
            'dominant_frequency': freqs[dominant_freq_idx]
        }
    
    def compute_channel_isolation(self, ch1_data, ch2_data):
        """Compute channel isolation metrics"""
        if len(ch1_data) != len(ch2_data) or len(ch1_data) == 0:
            return {}
            
        # Cross-talk analysis
        ch1_power = np.mean(ch1_data**2)
        ch2_power = np.mean(ch2_data**2)
        
        # Cross-correlation coefficient
        correlation_coeff = np.corrcoef(ch1_data, ch2_data)[0, 1]
        
        # Isolation in dB
        isolation_db = 10 * np.log10(max(ch1_power, ch2_power) / 
                                   (abs(correlation_coeff) * min(ch1_power, ch2_power) + 1e-12))
        
        return {
            'correlation_coefficient': correlation_coeff,
            'isolation_db': isolation_db,
            'ch1_power_db': 10 * np.log10(ch1_power + 1e-12),
            'ch2_power_db': 10 * np.log10(ch2_power + 1e-12)
        }
    
    def create_advanced_analysis_tab(self):
        """Create advanced analysis visualization"""
        if len(self.data_ch1) == 0:
            return pn.pane.Markdown("## No data available for advanced analysis")
        
        # Cross-correlation analysis
        corr, lags = self.compute_cross_correlation(self.data_ch1, self.data_ch2)
        
        # Pulse detection
        pulses_ch1 = self.detect_pulses(self.data_ch1)
        pulses_ch2 = self.detect_pulses(self.data_ch2)
        
        # Phase difference
        phase_analysis = self.compute_phase_difference(self.data_ch1, self.data_ch2)
        
        # Channel isolation
        isolation = self.compute_channel_isolation(self.data_ch1, self.data_ch2)
        
        # Create plots with enhanced styling
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.patch.set_facecolor('#f8f9fa')
        
        # Cross-correlation plot with gradient
        if len(corr) > 0:
            ax1.plot(lags * 1e6, corr, color='#28a745', linewidth=2.5, alpha=0.9, label='Cross-correlation')
            ax1.fill_between(lags * 1e6, corr, alpha=0.3, color='#28a745')
            ax1.set_xlabel('Lag Time (μs)', fontweight='bold')
            ax1.set_ylabel('Correlation Coefficient', fontweight='bold')
            ax1.set_title('Cross-Correlation Analysis', fontsize=12, fontweight='bold', pad=15)
            ax1.grid(True, alpha=0.4, linestyle='--')
            ax1.legend(framealpha=0.9)
            ax1.set_facecolor('#fafafa')
        
        # Phase difference plot with modern styling
        if 'frequencies' in phase_analysis and len(phase_analysis['frequencies']) > 0:
            freqs = phase_analysis['frequencies']
            phase_diff = phase_analysis['phase_diff_spectrum']
            pos_freqs = freqs[freqs > 0]
            pos_phase = phase_diff[freqs > 0]
            ax2.plot(pos_freqs/1e6, np.rad2deg(pos_phase), color='#dc3545', linewidth=2.5, alpha=0.9, label='Phase Difference')
            ax2.fill_between(pos_freqs/1e6, np.rad2deg(pos_phase), alpha=0.3, color='#dc3545')
            ax2.set_xlabel('Frequency (MHz)', fontweight='bold')
            ax2.set_ylabel('Phase Difference (°)', fontweight='bold')
            ax2.set_title('Phase Difference Spectrum', fontsize=12, fontweight='bold', pad=15)
            ax2.grid(True, alpha=0.4, linestyle='--')
            ax2.legend(framealpha=0.9)
            ax2.set_facecolor('#fafafa')
        
        # Pulse detection with enhanced visualization
        time_us = self.time_axis * 1e6
        ax3.plot(time_us, self.data_ch1, color='#4287f5', alpha=0.8, linewidth=1.5, label='CH1 Signal')
        ax3.fill_between(time_us, self.data_ch1, alpha=0.2, color='#4287f5')
        if pulses_ch1:
            pulse_times = [p['time'] * 1e6 for p in pulses_ch1]
            pulse_amps = [p['amplitude'] for p in pulses_ch1]
            ax3.scatter(pulse_times, pulse_amps, color='#ffc107', s=80, marker='*', 
                       edgecolors='#fd7e14', linewidth=2, label=f'Detected Pulses ({len(pulses_ch1)})')
        ax3.set_xlabel('Time (μs)', fontweight='bold')
        ax3.set_ylabel('Amplitude (V)', fontweight='bold')
        ax3.set_title('Pulse Detection Analysis', fontsize=12, fontweight='bold', pad=15)
        ax3.legend(framealpha=0.9)
        ax3.grid(True, alpha=0.4, linestyle='--')
        ax3.set_facecolor('#fafafa')
        
        # Channel isolation with gradient bars
        powers = [isolation.get('ch1_power_db', 0), isolation.get('ch2_power_db', 0), isolation.get('isolation_db', 0)]
        colors = ['#4287f5', '#ff6b6b', '#28a745']
        bars = ax4.bar(['CH1 Power', 'CH3 Power', 'Isolation'], powers, color=colors, alpha=0.8, 
                      edgecolor='white', linewidth=2)
        
        # Add value labels on bars
        for bar, power in zip(bars, powers):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{power:.1f} dB', ha='center', va='bottom', fontweight='bold')
        
        ax4.set_ylabel('Power Level (dB)', fontweight='bold')
        ax4.set_title('Channel Power & Isolation', fontsize=12, fontweight='bold', pad=15)
        ax4.grid(True, alpha=0.4, linestyle='--', axis='y')
        ax4.set_facecolor('#fafafa')
        
        plt.tight_layout(pad=3.0)
        
        # Create styled summary
        summary_html = f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 15px; padding: 25px; margin: 10px; 
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
            <h2 style="color: white; text-align: center; font-family: 'Arial', sans-serif; 
                       margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                🔬 Advanced Analysis Summary
            </h2>
            <div style="background: rgba(255,255,255,0.95); border-radius: 10px; padding: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-family: 'Arial', sans-serif;">
                    <div style="background: #f0f8ff; padding: 15px; border-radius: 8px; border-left: 4px solid #4287f5;">
                        <h3 style="color: #4287f5; margin: 0 0 15px 0;">🔄 Cross-Channel Analysis</h3>
                        <p><strong>Channel Isolation:</strong> <span style="color: #28a745; font-weight: bold;">{isolation.get('isolation_db', 0):.1f} dB</span></p>
                        <p><strong>Correlation Coefficient:</strong> <span style="color: #17a2b8; font-weight: bold;">{isolation.get('correlation_coefficient', 0):.3f}</span></p>
                        <p><strong>Phase Difference:</strong> <span style="color: #dc3545; font-weight: bold;">{np.rad2deg(phase_analysis.get('dominant_phase_diff', 0)):.1f}°</span></p>
                        <p><strong>Dominant Frequency:</strong> <span style="color: #6f42c1; font-weight: bold;">{phase_analysis.get('dominant_frequency', 0)/1e6:.3f} MHz</span></p>
                    </div>
                    <div style="background: #fff5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #ff6b6b;">
                        <h3 style="color: #ff6b6b; margin: 0 0 15px 0;">⚡ Signal Detection</h3>
                        <p><strong>CH1 Pulses:</strong> <span style="color: #4287f5; font-weight: bold;">{len(pulses_ch1)} detected</span></p>
                        <p><strong>CH3 Pulses:</strong> <span style="color: #ff6b6b; font-weight: bold;">{len(pulses_ch2)} detected</span></p>
                        <p><strong>Cross-correlation Max:</strong> <span style="color: #28a745; font-weight: bold;">{np.max(np.abs(corr)) if len(corr) > 0 else 0:.3f}</span></p>
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #17a2b8;">
                    <h3 style="color: #17a2b8; margin: 0 0 15px 0;">📊 Power Analysis</h3>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <p><strong>CH1 Power:</strong> <span style="color: #4287f5; font-weight: bold;">{isolation.get('ch1_power_db', 0):.1f} dB</span></p>
                        <p><strong>CH3 Power:</strong> <span style="color: #ff6b6b; font-weight: bold;">{isolation.get('ch2_power_db', 0):.1f} dB</span></p>
                        <p><strong>Isolation:</strong> <span style="color: #28a745; font-weight: bold;">{isolation.get('isolation_db', 0):.1f} dB</span></p>
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Combine plot and summary
        plot_pane = pn.pane.Matplotlib(fig, sizing_mode='stretch_both')
        summary_pane = pn.pane.HTML(summary_html, sizing_mode='stretch_width')
        
        return pn.Column(plot_pane, summary_pane)

def create_dashboard():
    """Create the main dashboard application"""
    
    # Initialize analytics class
    analytics = RFAnalytics()
    
    # Load initial data
    analytics.update_data()
    
    # Create interactive controls (safe approach)
    auto_refresh_toggle = pn.widgets.Toggle(name="Auto Refresh", value=analytics.auto_refresh, width=150)
    refresh_rate_slider = pn.widgets.FloatSlider(name="Refresh Rate (s)", start=0.1, end=10.0, step=0.1, value=analytics.refresh_rate, width=150)
    window_select = pn.widgets.Select(name="Window Function", options=['hann', 'hamming', 'blackman', 'bartlett', 'none'], value=analytics.window_function, width=150)
    fft_size_select = pn.widgets.Select(name="FFT Size", options=[1024, 2048, 4096, 8192, 16384], value=analytics.fft_size, width=150)
    freq_low_input = pn.widgets.FloatInput(name="Freq Low (MHz)", value=analytics.freq_range_low/1e6, width=150)
    freq_high_input = pn.widgets.FloatInput(name="Freq High (MHz)", value=analytics.freq_range_high/1e6, width=150)
    
    # Update callbacks
    def update_auto_refresh(event):
        analytics.auto_refresh = event.new
    def update_refresh_rate(event):
        analytics.refresh_rate = event.new
    def update_window(event):
        analytics.window_function = event.new
    def update_fft_size(event):
        analytics.fft_size = event.new
    def update_freq_low(event):
        analytics.freq_range_low = event.new * 1e6
    def update_freq_high(event):
        analytics.freq_range_high = event.new * 1e6
    
    # Bind callbacks
    auto_refresh_toggle.param.watch(update_auto_refresh, 'value')
    refresh_rate_slider.param.watch(update_refresh_rate, 'value')
    window_select.param.watch(update_window, 'value')
    fft_size_select.param.watch(update_fft_size, 'value')
    freq_low_input.param.watch(update_freq_low, 'value')
    freq_high_input.param.watch(update_freq_high, 'value')
    
    controls = pn.Column(
        auto_refresh_toggle,
        refresh_rate_slider,
        window_select,
        fft_size_select,
        freq_low_input,
        freq_high_input,
        width=200
    )
    
    # Refresh button
    refresh_button = pn.widgets.Button(name="🔄 Refresh Data", button_type="primary")
    
    def refresh_callback(event):
        analytics.update_data()
        
    refresh_button.on_click(refresh_callback)
    
    # Create simple static functions (will update via refresh button)
    def time_plot():
        return analytics.create_time_domain_plot()
    
    def freq_plot():
        return analytics.create_frequency_domain_plot()
    
    def metrics_table():
        return analytics.create_metrics_table()
    
    def advanced_analysis():
        return analytics.create_advanced_analysis_tab()
    
    def status_panel():
        return analytics.create_status_panel()
    
    # Create styled tabs
    tabs = pn.Tabs(
        ("📈 Time Domain", time_plot),
        ("🎛️ Frequency Domain", freq_plot), 
        ("📊 Metrics", metrics_table),
        ("🔬 Advanced Analysis", advanced_analysis),
        ("ℹ️ Status", status_panel),
        dynamic=False,
        styles={
            'background': '#ffffff',
            'border-radius': '10px',
            'box-shadow': '0 4px 20px rgba(0,0,0,0.1)',
            'border': '1px solid #dee2e6'
        }
    )
    
    # Create styled sidebar
    header_html = """
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 12px; padding: 20px; margin-bottom: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
        <h1 style="color: white; text-align: center; font-family: 'Arial Black', sans-serif; 
                   margin: 0; font-size: 18px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
            📡 RF Analytics Dashboard
        </h1>
        <p style="color: rgba(255,255,255,0.9); text-align: center; margin: 5px 0 0 0; 
                  font-size: 12px; font-style: italic;">
            PCI-9846H Real-time Analysis
        </p>
    </div>
    """
    
    sidebar = pn.Column(
        pn.pane.HTML(header_html),
        pn.pane.HTML('<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4287f5;"><h3 style="color: #4287f5; margin: 0 0 10px 0;">⚙️ Control Panel</h3></div>'),
        controls,
        pn.Spacer(height=15),
        refresh_button,
        width=370,
        styles={
            'background': 'linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%)',
            'padding': '20px',
            'border-radius': '15px',
            'box-shadow': '0 4px 20px rgba(0,0,0,0.1)',
            'border': '1px solid #dee2e6'
        }
    )
    
    main_area = pn.Column(
        tabs,
        sizing_mode='stretch_width',
        styles={
            'background': '#f8f9fa',
            'padding': '20px',
            'border-radius': '15px',
            'margin': '0 0 0 20px'
        }
    )
    
    # Setup auto-refresh callback (will be handled by user interaction)
    def auto_refresh_callback():
        if analytics.auto_refresh:
            analytics.update_data()
    
    # Note: Auto-refresh will be triggered by parameter changes and manual refresh button
    
    template = pn.Row(
        sidebar,
        main_area,
        sizing_mode='stretch_width',
        styles={
            'background': 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
            'padding': '20px',
            'min-height': '100vh'
        }
    )
    
    return template

if __name__ == "__main__":
    # Create and serve dashboard
    dashboard = create_dashboard()
    dashboard.servable()
    
    # For standalone running with extended session token expiration
    dashboard.show(
        port=5007, 
        autoreload=True,
        session_token_expiration=3600000,  # 1 hour in milliseconds
        allow_websocket_origin=["localhost:5007", "127.0.0.1:5007"]
    )