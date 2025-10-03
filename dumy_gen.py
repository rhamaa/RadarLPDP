"""Dummy data generator for testing radar acquisition system.

This script generates simulated RF data with varying frequencies to test
the radar UI without actual hardware. Data is written in the same format
as the real ADC: interleaved CH1/CH3 samples as uint16.
"""

import os
import struct
import time
from pathlib import Path

import numpy as np

from config import FILENAME, SAMPLE_RATE, BUFFER_SAMPLES

# Signal generation parameters
CH1_BASE_FREQ: int = 900_000  # 900 kHz
CH1_JITTER: int = 1_000       # ±1 kHz variation
CH2_BASE_FREQ: int = 1_500_000  # 1.5 MHz
CH2_JITTER: int = 2_000       # ±2 kHz variation

# Signal amplitudes (uint16 range)
CH1_AMPLITUDE: int = 1000
CH2_AMPLITUDE: int = 800

# Update interval
UPDATE_INTERVAL: float = 0.05  # 50ms (~20 Hz update rate)


def generate_signal(
    frequency: float,
    amplitude: int,
    num_samples: int,
    sample_rate: int
) -> np.ndarray:
    """Generate a sinusoidal signal.
    
    Args:
        frequency: Signal frequency in Hz
        amplitude: Signal amplitude
        num_samples: Number of samples to generate
        sample_rate: Sample rate in Hz
        
    Returns:
        Signal array as uint16
    """
    t = np.linspace(0, num_samples / sample_rate, num_samples, endpoint=False)
    signal = amplitude * np.sin(2 * np.pi * frequency * t)
    return signal.astype(np.uint16)


def create_interleaved_data(
    ch1_data: np.ndarray,
    ch2_data: np.ndarray
) -> np.ndarray:
    """Interleave two channel data arrays.
    
    Args:
        ch1_data: Channel 1 data
        ch2_data: Channel 2 data
        
    Returns:
        Interleaved data array [CH1_0, CH2_0, CH1_1, CH2_1, ...]
    """
    num_samples = len(ch1_data)
    interleaved = np.empty(num_samples * 2, dtype=np.uint16)
    interleaved[0::2] = ch1_data
    interleaved[1::2] = ch2_data
    return interleaved


def main() -> None:
    """Main simulation loop."""
    # Ensure output directory exists
    output_path = Path(FILENAME)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting RF data simulation")
    print(f"Output file: {FILENAME}")
    print(f"Update rate: {1/UPDATE_INTERVAL:.1f} Hz")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Generate frequencies with random jitter
            freq1 = CH1_BASE_FREQ + np.random.randint(-CH1_JITTER, CH1_JITTER + 1)
            freq2 = CH2_BASE_FREQ + np.random.randint(-CH2_JITTER, CH2_JITTER + 1)
            
            # Generate signals
            signal1 = generate_signal(freq1, CH1_AMPLITUDE, BUFFER_SAMPLES, SAMPLE_RATE)
            signal2 = generate_signal(freq2, CH2_AMPLITUDE, BUFFER_SAMPLES, SAMPLE_RATE)
            
            # Interleave data (same format as real hardware)
            interleaved_data = create_interleaved_data(signal1, signal2)

            # Write to binary file
            with open(FILENAME, "wb") as f:
                f.write(struct.pack(f'<{len(interleaved_data)}H', *interleaved_data))
            
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"CH1: {freq1/1000:.1f} kHz | "
                f"CH2: {freq2/1000:.1f} kHz"
            )
            
            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped.")


if __name__ == "__main__":
    main()