"""Dummy data generator for testing radar acquisition system with UI controls.

OVERVIEW:
=========
This script generates simulated RF data with controllable moving target peaks
to test the radar UI without actual hardware. Data is written in the same format
as the real ADC: interleaved CH1/CH3 samples as uint16.

ARCHITECTURE:
=============
1. SimulationState: Thread-safe state manager for all parameters
2. simulation_loop(): Background thread that generates and writes data
3. RadarSimulatorUI: Tkinter GUI for real-time parameter control
4. Signal generation: Creates peaks at specific FFT indices to simulate targets

KEY CONCEPT - FFT Index to Target Simulation:
==============================================
To simulate a target at a specific distance, we generate a sinusoid at the
corresponding frequency:

    target_freq = (fft_index / FFT_SIZE) * SAMPLE_RATE
    signal = amplitude * sin(2π * target_freq * t)

This creates a peak in the FFT at the desired index, which calculate_target_distance()
will detect and map to distance:

    normalized = (index - index_min) / (index_max - index_min)
    distance = normalized * max_range

USAGE:
======
1. Run: python dumy_gen_ui.py
2. Adjust CH1/CH3 parameters in UI (real-time, langsung apply):
   - Amplitude: Signal strength in dB (30-120 dB)
   - Index Min/Max: Range of movement (1000-4096)
   - Enable/Disable: Turn targets on/off
3. Set movement speed (1-50 indices per update)
4. Click "Start Simulation"
5. Targets will move back-and-forth within configured ranges
6. Adjust parameters WHILE running → changes apply immediately to output .bin

FEATURES:
=========
- Tkinter UI for real-time control
- dB-based amplitude control (30-120 dB) for CH1 and CH3
- Configurable target movement range (FFT index)
- Variable movement speed (1-50 indices/update)
- Independent enable/disable per channel
- Thread-safe parameter updates with immediate effect
- Real-time position monitoring
- On-the-fly parameter adjustment (no need to stop/restart)

OUTPUT FORMAT:
==============
File: live/live_acquisition_ui.bin (configurable via config.py)
Format: Interleaved CH1, CH3 as uint16 little-endian
Structure: [CH1_0, CH3_0, CH1_1, CH3_1, ..., CH1_8191, CH3_8191]
Total: 16384 uint16 values = 32768 bytes per frame
Update Rate: ~20 Hz (50ms interval)

SIGNAL GENERATION DETAILS:
===========================
- DC Offset: 32768 (mid-point of uint16 range)
- Target Signal: amplitude * sin(2π * freq * t)
- Background Noise: Gaussian noise with configurable std dev
- Combined: DC + target + noise, clamped to [0, 65535]

EXAMPLE SCENARIOS:
==================
1. Single Target at 50m:
   - CH1: Enable, Amplitude=85 dB, Index=3000-3100, Speed=5
   - CH3: Disable
   
2. Two Targets (near & far):
   - CH1: Enable, Index=2600-2800 (near), Amplitude=80 dB
   - CH3: Enable, Index=3800-4000 (far), Amplitude=75 dB
   
3. Fast Moving Target:
   - CH1: Enable, Index=2500-4000 (full range), Amplitude=90 dB, Speed=40
   - CH3: Disable

4. Weak Signal Testing (threshold testing):
   - CH1: Enable, Amplitude=50 dB (weak), Index=3000-3200, Speed=5
   - CH3: Disable
   - Adjust amplitude up until detected (biasanya >65 dB)

5. Strong Signal Multiple Targets:
   - CH1: Enable, Amplitude=100 dB, Index=2500-3000
   - CH3: Enable, Amplitude=95 dB, Index=3500-4000
   - Speed=20

TROUBLESHOOTING:
================
- Target not detected: Increase amplitude (>70 dB) or check index range (2500-4096)
- Weak signal: Default detection threshold ~65 dB, naikkan amplitude di UI
- UI unresponsive: Parameter changes are real-time, no need to stop/restart
- No data written: Check folder permissions for 'live/' directory
- Erratic behavior: Lower movement speed or reduce noise level
- Real-time not working: Check state.lock implementation (already thread-safe)

TECHNICAL NOTES:
================
- FFT Size: 8192 samples
- Sample Rate: 20 MHz
- Freq Resolution: ~2.44 kHz/bin
- Detection Range: Index 2500-4096 → 6.1-10.0 MHz
- Amplitude Range: 30-120 dB (converted to linear: 10^(dB/20))
- dB Conversion Examples:
  * 30 dB → amplitude ~31.6
  * 60 dB → amplitude ~1000
  * 80 dB → amplitude ~10000
  * 100 dB → amplitude ~100000
  * 120 dB → amplitude ~1000000
- Thread Model: UI in main thread, generation in background daemon thread
- State Sync: Lock-based synchronization between threads
- Real-time Update: Slider changes instantly apply via state.lock (thread-safe)
- Update Latency: <50ms (next frame akan gunakan nilai baru)

AUTHOR: Raihan Muhammad - Radar LPDP Project
VERSION: 2.0 - dB Control & Real-time Update
"""

import os
import struct
import time
import threading
from pathlib import Path
from typing import Dict, Any
import tkinter as tk
from tkinter import ttk

import numpy as np

from config import FILENAME, SAMPLE_RATE, BUFFER_SAMPLES

# FFT parameters (must match processing side)
FFT_SIZE: int = BUFFER_SAMPLES  # 8192
FREQ_RESOLUTION: float = SAMPLE_RATE / FFT_SIZE  # ~2441 Hz per bin

# Update interval
UPDATE_INTERVAL: float = 0.05  # 50ms (~20 Hz update rate)

# Default signal parameters (in dB)
DEFAULT_CH1_AMPLITUDE_DB: float = 80.0  # dB
DEFAULT_CH3_AMPLITUDE_DB: float = 75.0  # dB
DEFAULT_NOISE_LEVEL: int = 100
DEFAULT_INDEX_MIN: int = 2500
DEFAULT_INDEX_MAX: int = 4000
DEFAULT_MOVEMENT_SPEED: int = 10  # indices per update

# Amplitude dB range
AMPLITUDE_DB_MIN: float = 30.0
AMPLITUDE_DB_MAX: float = 120.0
AMPLITUDE_REFERENCE: float = 1.0  # Reference for dB conversion

def db_to_linear_amplitude(db: float, reference: float = AMPLITUDE_REFERENCE) -> float:
    """Convert dB to linear amplitude.
    
    Formula: amplitude = reference * 10^(dB/20)
    
    Args:
        db: Amplitude in decibels
        reference: Reference amplitude (default 1.0)
        
    Returns:
        Linear amplitude value
    
    Example:
        80 dB -> ~10000 linear amplitude
        60 dB -> ~1000 linear amplitude
    """
    return reference * (10.0 ** (db / 20.0))


# Simulation state - will be controlled by UI
class SimulationState:
    """Thread-safe simulation state.
    
    Note: Amplitudes are stored in dB and converted to linear when generating signals.
    This allows for more intuitive control and better dynamic range.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        
        # CH1 settings (amplitude in dB)
        self.ch1_amplitude_db = DEFAULT_CH1_AMPLITUDE_DB
        self.ch1_index_min = DEFAULT_INDEX_MIN
        self.ch1_index_max = DEFAULT_INDEX_MAX
        self.ch1_enabled = True
        self.ch1_current_index = DEFAULT_INDEX_MIN
        self.ch1_direction = 1  # 1 = forward, -1 = backward
        
        # CH3 settings (amplitude in dB)
        self.ch3_amplitude_db = DEFAULT_CH3_AMPLITUDE_DB
        self.ch3_index_min = DEFAULT_INDEX_MIN
        self.ch3_index_max = DEFAULT_INDEX_MAX + 500  # Offset untuk variasi
        self.ch3_enabled = True
        self.ch3_current_index = DEFAULT_INDEX_MIN
        self.ch3_direction = 1
        
        # Movement settings
        self.movement_speed = DEFAULT_MOVEMENT_SPEED
        self.noise_level = DEFAULT_NOISE_LEVEL
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state snapshot with linear amplitude conversion."""
        with self.lock:
            return {
                'ch1_amplitude_db': self.ch1_amplitude_db,
                'ch1_amplitude': db_to_linear_amplitude(self.ch1_amplitude_db),
                'ch1_index_min': self.ch1_index_min,
                'ch1_index_max': self.ch1_index_max,
                'ch1_enabled': self.ch1_enabled,
                'ch1_current_index': self.ch1_current_index,
                'ch3_amplitude_db': self.ch3_amplitude_db,
                'ch3_amplitude': db_to_linear_amplitude(self.ch3_amplitude_db),
                'ch3_index_min': self.ch3_index_min,
                'ch3_index_max': self.ch3_index_max,
                'ch3_enabled': self.ch3_enabled,
                'ch3_current_index': self.ch3_current_index,
                'movement_speed': self.movement_speed,
                'noise_level': self.noise_level,
            }
    
    def update_ch1(self, **kwargs):
        """Update CH1 parameters."""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self, f'ch1_{key}'):
                    setattr(self, f'ch1_{key}', value)
    
    def update_ch3(self, **kwargs):
        """Update CH3 parameters."""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self, f'ch3_{key}'):
                    setattr(self, f'ch3_{key}', value)
    
    def update_movement(self, speed: int):
        """Update movement speed."""
        with self.lock:
            self.movement_speed = speed

    def update_noise(self, level: int):
        """Update noise level."""
        with self.lock:
            self.noise_level = level


# Global state instance
state = SimulationState()


def generate_signal_with_target(
    target_index: int,
    amplitude: int,
    noise_level: int,
    num_samples: int,
    sample_rate: int
) -> np.ndarray:
    """Generate signal with a target peak at specific FFT index.
    
    Args:
        target_index: FFT bin index where target peak should appear
        amplitude: Target signal amplitude
        noise_level: Background noise level
        num_samples: Number of samples to generate
        sample_rate: Sample rate in Hz
        
    Returns:
        Signal array as uint16 with DC offset
    """
    # Calculate target frequency from FFT index
    # frequency = (index / fft_size) * sample_rate
    target_freq = (target_index / num_samples) * sample_rate
    
    # Generate time vector
    t = np.linspace(0, num_samples / sample_rate, num_samples, endpoint=False)
    
    # Generate target signal (sinusoid at target frequency)
    target_signal = amplitude * np.sin(2 * np.pi * target_freq * t)
    
    # Add background noise
    noise = np.random.normal(0, noise_level, num_samples)
    
    # Combine signals with DC offset (32768 = midpoint of uint16 range)
    combined = 32768 + target_signal + noise
    
    # Clamp to uint16 range
    combined = np.clip(combined, 0, 65535)
    
    return combined.astype(np.uint16)


def update_target_position(
    current_index: int,
    direction: int,
    speed: int,
    index_min: int,
    index_max: int
) -> tuple[int, int]:
    """Update target position with bounce-back behavior.
    
    Args:
        current_index: Current FFT index
        direction: Movement direction (1 or -1)
        speed: Movement speed in indices per update
        index_min: Minimum index boundary
        index_max: Maximum index boundary
        
    Returns:
        Tuple of (new_index, new_direction)
    """
    new_index = current_index + (direction * speed)
    new_direction = direction
    
    # Bounce at boundaries
    if new_index >= index_max:
        new_index = index_max
        new_direction = -1
    elif new_index <= index_min:
        new_index = index_min
        new_direction = 1
    
    return new_index, new_direction


def create_interleaved_data(
    ch1_data: np.ndarray,
    ch2_data: np.ndarray
) -> np.ndarray:
    """Interleave two channel data arrays.
    
    Args:
        ch1_data: Channel 1 data
        ch2_data: Channel 2 data (actually CH3 in hardware)
        
    Returns:
        Interleaved data array [CH1_0, CH2_0, CH1_1, CH2_1, ...]
    """
    num_samples = len(ch1_data)
    interleaved = np.empty(num_samples * 2, dtype=np.uint16)
    interleaved[0::2] = ch1_data
    interleaved[1::2] = ch2_data
    return interleaved


def simulation_loop() -> None:
    """Main simulation loop running in background thread."""
    # Ensure output directory exists
    output_path = Path(FILENAME)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("🎯 RF Data Simulator - Moving Target Mode with UI Control")
    print("=" * 80)
    print(f"Output file: {FILENAME}")
    print(f"Update rate: {1/UPDATE_INTERVAL:.1f} Hz")
    print(f"FFT Size: {FFT_SIZE} samples")
    print(f"Frequency resolution: {FREQ_RESOLUTION/1e3:.2f} kHz/bin")
    print("=" * 80)
    print("\n⚙️  Use the UI to control simulation parameters.\n")

    iteration = 0
    try:
        while state.running:
            iteration += 1
            
            # Get current state snapshot
            current_state = state.get_state()
            
            # Generate CH1 signal
            if current_state['ch1_enabled']:
                signal_ch1 = generate_signal_with_target(
                    target_index=current_state['ch1_current_index'],
                    amplitude=current_state['ch1_amplitude'],
                    noise_level=current_state['noise_level'],
                    num_samples=BUFFER_SAMPLES,
                    sample_rate=SAMPLE_RATE
                )
                
                # Update CH1 position
                with state.lock:
                    state.ch1_current_index, state.ch1_direction = update_target_position(
                        current_index=state.ch1_current_index,
                        direction=state.ch1_direction,
                        speed=state.movement_speed,
                        index_min=state.ch1_index_min,
                        index_max=state.ch1_index_max
                    )
            else:
                # Just noise if disabled
                signal_ch1 = np.random.normal(
                    32768, 
                    current_state['noise_level'], 
                    BUFFER_SAMPLES
                ).clip(0, 65535).astype(np.uint16)
            
            # Generate CH3 signal (note: hardware uses CH3, not CH2)
            if current_state['ch3_enabled']:
                signal_ch3 = generate_signal_with_target(
                    target_index=current_state['ch3_current_index'],
                    amplitude=current_state['ch3_amplitude'],
                    noise_level=current_state['noise_level'],
                    num_samples=BUFFER_SAMPLES,
                    sample_rate=SAMPLE_RATE
                )
                
                # Update CH3 position
                with state.lock:
                    state.ch3_current_index, state.ch3_direction = update_target_position(
                        current_index=state.ch3_current_index,
                        direction=state.ch3_direction,
                        speed=state.movement_speed,
                        index_min=state.ch3_index_min,
                        index_max=state.ch3_index_max
                    )
            else:
                # Just noise if disabled
                signal_ch3 = np.random.normal(
                    32768,
                    current_state['noise_level'],
                    BUFFER_SAMPLES
                ).clip(0, 65535).astype(np.uint16)
            
            # Interleave data (CH1, CH3 - matches hardware format)
            interleaved_data = create_interleaved_data(signal_ch1, signal_ch3)

            # Write to binary file
            with open(FILENAME, "wb") as f:
                f.write(struct.pack(f'<{len(interleaved_data)}H', *interleaved_data))
            
            # Print status every 20 iterations (~1 second)
            if iteration % 20 == 0:
                ch1_freq = (current_state['ch1_current_index'] / FFT_SIZE) * SAMPLE_RATE / 1e6
                ch3_freq = (current_state['ch3_current_index'] / FFT_SIZE) * SAMPLE_RATE / 1e6
                
                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"CH1: idx={current_state['ch1_current_index']:4d} ({ch1_freq:5.2f} MHz) | "
                    f"CH3: idx={current_state['ch3_current_index']:4d} ({ch3_freq:5.2f} MHz)"
                )
            
            time.sleep(UPDATE_INTERVAL)

    except Exception as e:
        print(f"\n❌ Error in simulation loop: {e}")
        state.running = False
    
    print("\n" + "=" * 80)
    print("✅ Simulation stopped.")
    print(f"📊 Total iterations: {iteration}")
    print(f"⏱️  Total time: {iteration * UPDATE_INTERVAL:.1f} seconds")
    print("=" * 80)


class RadarSimulatorUI:
    """Tkinter UI for controlling radar simulation parameters."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎯 Radar Target Simulator Control Panel")
        self.root.geometry("900x750")
        
        self.sim_thread = None
        
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        """Create all UI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(
            main_frame, 
            text="Radar Target Simulator Control",
            font=('Arial', 16, 'bold')
        )
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # CH1 Frame
        ch1_frame = ttk.LabelFrame(main_frame, text="📡 Channel 1 (CH1)", padding="10")
        ch1_frame.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.ch1_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ch1_frame, 
            text="Enable Target",
            variable=self.ch1_enabled_var,
            command=self.on_ch1_enabled_changed
        ).grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(ch1_frame, text="Amplitude (dB):").grid(row=1, column=0, sticky=tk.W)
        self.ch1_amp_scale = ttk.Scale(
            ch1_frame, from_=AMPLITUDE_DB_MIN, to=AMPLITUDE_DB_MAX, orient=tk.HORIZONTAL
        )
        self.ch1_amp_scale.set(DEFAULT_CH1_AMPLITUDE_DB)
        self.ch1_amp_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch1_amp_label = ttk.Label(ch1_frame, text=f"{DEFAULT_CH1_AMPLITUDE_DB:.1f} dB")
        self.ch1_amp_label.grid(row=1, column=2)
        
        ttk.Label(ch1_frame, text="Index Min:").grid(row=2, column=0, sticky=tk.W)
        self.ch1_min_scale = ttk.Scale(
            ch1_frame, from_=1000, to=4000, orient=tk.HORIZONTAL
        )
        self.ch1_min_scale.set(DEFAULT_INDEX_MIN)
        self.ch1_min_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch1_min_label = ttk.Label(ch1_frame, text=f"{DEFAULT_INDEX_MIN}")
        self.ch1_min_label.grid(row=2, column=2)
        
        ttk.Label(ch1_frame, text="Index Max:").grid(row=3, column=0, sticky=tk.W)
        self.ch1_max_scale = ttk.Scale(
            ch1_frame, from_=1000, to=4096, orient=tk.HORIZONTAL
        )
        self.ch1_max_scale.set(DEFAULT_INDEX_MAX)
        self.ch1_max_scale.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch1_max_label = ttk.Label(ch1_frame, text=f"{DEFAULT_INDEX_MAX}")
        self.ch1_max_label.grid(row=3, column=2)
        
        self.ch1_status_label = ttk.Label(
            ch1_frame, 
            text="Current: Index 2500 (6.10 MHz)",
            foreground="blue"
        )
        self.ch1_status_label.grid(row=4, column=0, columnspan=3, pady=5)
        
        # CH3 Frame
        ch3_frame = ttk.LabelFrame(main_frame, text="📡 Channel 3 (CH3)", padding="10")
        ch3_frame.grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.ch3_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ch3_frame,
            text="Enable Target",
            variable=self.ch3_enabled_var,
            command=self.on_ch3_enabled_changed
        ).grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(ch3_frame, text="Amplitude (dB):").grid(row=1, column=0, sticky=tk.W)
        self.ch3_amp_scale = ttk.Scale(
            ch3_frame, from_=AMPLITUDE_DB_MIN, to=AMPLITUDE_DB_MAX, orient=tk.HORIZONTAL
        )
        self.ch3_amp_scale.set(DEFAULT_CH3_AMPLITUDE_DB)
        self.ch3_amp_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch3_amp_label = ttk.Label(ch3_frame, text=f"{DEFAULT_CH3_AMPLITUDE_DB:.1f} dB")
        self.ch3_amp_label.grid(row=1, column=2)
        
        ttk.Label(ch3_frame, text="Index Min:").grid(row=2, column=0, sticky=tk.W)
        self.ch3_min_scale = ttk.Scale(
            ch3_frame, from_=1000, to=4000, orient=tk.HORIZONTAL
        )
        self.ch3_min_scale.set(DEFAULT_INDEX_MIN)
        self.ch3_min_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch3_min_label = ttk.Label(ch3_frame, text=f"{DEFAULT_INDEX_MIN}")
        self.ch3_min_label.grid(row=2, column=2)
        
        ttk.Label(ch3_frame, text="Index Max:").grid(row=3, column=0, sticky=tk.W)
        self.ch3_max_scale = ttk.Scale(
            ch3_frame, from_=1000, to=4096, orient=tk.HORIZONTAL
        )
        self.ch3_max_scale.set(DEFAULT_INDEX_MAX + 500)
        self.ch3_max_scale.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ch3_max_label = ttk.Label(ch3_frame, text=f"{DEFAULT_INDEX_MAX + 500}")
        self.ch3_max_label.grid(row=3, column=2)
        
        self.ch3_status_label = ttk.Label(
            ch3_frame,
            text="Current: Index 2500 (6.10 MHz)",
            foreground="blue"
        )
        self.ch3_status_label.grid(row=4, column=0, columnspan=3, pady=5)
        
        # Movement Settings Frame
        movement_frame = ttk.LabelFrame(main_frame, text="🎮 Movement Settings", padding="10")
        movement_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(movement_frame, text="Movement Speed (indices/update):").grid(row=0, column=0, sticky=tk.W)
        self.speed_scale = ttk.Scale(
            movement_frame, from_=1, to=50, orient=tk.HORIZONTAL
        )
        self.speed_scale.set(DEFAULT_MOVEMENT_SPEED)
        self.speed_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.speed_label = ttk.Label(movement_frame, text=f"{DEFAULT_MOVEMENT_SPEED}")
        self.speed_label.grid(row=0, column=2)
        
        ttk.Label(movement_frame, text="Noise Level:").grid(row=1, column=0, sticky=tk.W)
        self.noise_scale = ttk.Scale(
            movement_frame, from_=10, to=500, orient=tk.HORIZONTAL
        )
        self.noise_scale.set(DEFAULT_NOISE_LEVEL)
        self.noise_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.noise_label = ttk.Label(movement_frame, text=f"{DEFAULT_NOISE_LEVEL}")
        self.noise_label.grid(row=1, column=2)
        
        # Control Buttons Frame
        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(
            control_frame,
            text="▶️ Start Simulation",
            command=self.start_simulation,
            width=20
        )
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(
            control_frame,
            text="⏹️ Stop Simulation",
            command=self.stop_simulation,
            state=tk.DISABLED,
            width=20
        )
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # Status Display
        status_frame = ttk.LabelFrame(main_frame, text="📊 System Status", padding="10")
        status_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        self.status_text = tk.Text(status_frame, height=6, width=80, state=tk.DISABLED)
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.update_status_text("Ready to start simulation...")
        
        # Info Label
        info_text = (
            "ℹ️ Info: Target peaks akan bergerak bolak-balik dalam range yang ditentukan.\n"
            "Amplitude: 30-120 dB (real-time control, langsung apply ke output .bin)\n"
            "FFT Index → Frequency: freq(MHz) = (index / 8192) × 20 MHz\n"
            "Range deteksi default: 2500-4096 → 6.1-10.0 MHz"
        )
        info_label = ttk.Label(main_frame, text=info_text, foreground="gray", justify=tk.LEFT)
        info_label.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Attach scale callbacks AFTER all widgets are created
        # to avoid AttributeError when .set() triggers callback before labels exist
        self.ch1_amp_scale.config(command=lambda v: self.on_ch1_amplitude_changed(float(v)))
        self.ch1_min_scale.config(command=lambda v: self.on_ch1_min_changed(float(v)))
        self.ch1_max_scale.config(command=lambda v: self.on_ch1_max_changed(float(v)))
        self.ch3_amp_scale.config(command=lambda v: self.on_ch3_amplitude_changed(float(v)))
        self.ch3_min_scale.config(command=lambda v: self.on_ch3_min_changed(float(v)))
        self.ch3_max_scale.config(command=lambda v: self.on_ch3_max_changed(float(v)))
        self.speed_scale.config(command=lambda v: self.on_speed_changed(float(v)))
        self.noise_scale.config(command=lambda v: self.on_noise_changed(float(v)))
    
    # Event handlers
    def on_ch1_enabled_changed(self):
        enabled = self.ch1_enabled_var.get()
        state.update_ch1(enabled=enabled)
        self.update_status_text(f"CH1 target {'enabled' if enabled else 'disabled'}")
    
    def on_ch1_amplitude_changed(self, value):
        amp_db = float(value)
        with state.lock:
            state.ch1_amplitude_db = amp_db
        self.ch1_amp_label.config(text=f"{amp_db:.1f} dB")
        # Real-time: perubahan langsung apply karena state.lock thread-safe
    
    def on_ch1_min_changed(self, value):
        min_idx = int(value)
        state.update_ch1(index_min=min_idx)
        self.ch1_min_label.config(text=f"{min_idx}")
        # Update current index if it's below new min
        with state.lock:
            if state.ch1_current_index < min_idx:
                state.ch1_current_index = min_idx
    
    def on_ch1_max_changed(self, value):
        max_idx = int(value)
        state.update_ch1(index_max=max_idx)
        self.ch1_max_label.config(text=f"{max_idx}")
        # Update current index if it's above new max
        with state.lock:
            if state.ch1_current_index > max_idx:
                state.ch1_current_index = max_idx
    
    def on_ch3_enabled_changed(self):
        enabled = self.ch3_enabled_var.get()
        state.update_ch3(enabled=enabled)
        self.update_status_text(f"CH3 target {'enabled' if enabled else 'disabled'}")
    
    def on_ch3_amplitude_changed(self, value):
        amp_db = float(value)
        with state.lock:
            state.ch3_amplitude_db = amp_db
        self.ch3_amp_label.config(text=f"{amp_db:.1f} dB")
        # Real-time: perubahan langsung apply karena state.lock thread-safe
    
    def on_ch3_min_changed(self, value):
        min_idx = int(value)
        state.update_ch3(index_min=min_idx)
        self.ch3_min_label.config(text=f"{min_idx}")
        with state.lock:
            if state.ch3_current_index < min_idx:
                state.ch3_current_index = min_idx
    
    def on_ch3_max_changed(self, value):
        max_idx = int(value)
        state.update_ch3(index_max=max_idx)
        self.ch3_max_label.config(text=f"{max_idx}")
        with state.lock:
            if state.ch3_current_index > max_idx:
                state.ch3_current_index = max_idx
    
    def on_speed_changed(self, value):
        speed = int(value)
        state.update_movement(speed)
        self.speed_label.config(text=f"{speed}")
    
    def on_noise_changed(self, value):
        noise = int(value)
        state.update_noise(noise)
        self.noise_label.config(text=f"{noise}")
    
    def start_simulation(self):
        """Start the simulation in a background thread."""
        if not state.running:
            state.running = True
            self.sim_thread = threading.Thread(target=simulation_loop, daemon=True)
            self.sim_thread.start()
            
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_status_text("✅ Simulation started")
    
    def stop_simulation(self):
        """Stop the simulation."""
        if state.running:
            state.running = False
            if self.sim_thread:
                self.sim_thread.join(timeout=2.0)
            
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status_text("⏹️ Simulation stopped")
    
    def update_status_text(self, message: str):
        """Update the status text display."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def update_display(self):
        """Periodically update the display with current positions."""
        if state.running:
            current_state = state.get_state()
            
            # Update CH1 status
            ch1_idx = current_state['ch1_current_index']
            ch1_freq = (ch1_idx / FFT_SIZE) * SAMPLE_RATE / 1e6
            self.ch1_status_label.config(
                text=f"Current: Index {ch1_idx} ({ch1_freq:.2f} MHz)"
            )
            
            # Update CH3 status
            ch3_idx = current_state['ch3_current_index']
            ch3_freq = (ch3_idx / FFT_SIZE) * SAMPLE_RATE / 1e6
            self.ch3_status_label.config(
                text=f"Current: Index {ch3_idx} ({ch3_freq:.2f} MHz)"
            )
        
        # Schedule next update
        self.root.after(100, self.update_display)
    
    def on_closing(self):
        """Handle window close event."""
        if state.running:
            self.stop_simulation()
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = RadarSimulatorUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
