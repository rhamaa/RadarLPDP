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
CH1_BASE_FREQ: int = 900_000      # 900 kHz (low freq baseline)
CH1_JITTER: int = 1_000           # ±1 kHz variation

# CH2 simulates FMCW radar return (>10 MHz for target detection)
CH2_BASE_FREQ: int = 12_000_000   # 12 MHz center frequency
CH2_BANDWIDTH: int = 2_000_000    # 2 MHz sweep bandwidth
CH2_SWEEP_TIME: float = 0.001     # 1 ms sweep time (1 kHz sweep rate)

# Signal amplitudes (uint16 range)
CH1_AMPLITUDE: int = 1000
CH2_AMPLITUDE: int = 800

# Update interval
UPDATE_INTERVAL: float = 0.05  # 50ms (~20 Hz update rate)

# FMCW simulation state
_fmcw_phase: float = 0.0  # Current phase in sweep cycle


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


def generate_fmcw_signal(
    center_freq: float,
    bandwidth: float,
    sweep_time: float,
    amplitude: int,
    num_samples: int,
    sample_rate: int,
    phase_offset: float = 0.0
) -> tuple[np.ndarray, float]:
    """Generate FMCW (Frequency Modulated Continuous Wave) signal.
    
    FMCW radar sweeps frequency linearly from (f_center - BW/2) to (f_center + BW/2).
    This simulates a realistic radar return signal.
    
    Args:
        center_freq: Center frequency in Hz
        bandwidth: Sweep bandwidth in Hz
        sweep_time: Time for one complete sweep in seconds
        amplitude: Signal amplitude
        num_samples: Number of samples to generate
        sample_rate: Sample rate in Hz
        phase_offset: Starting phase offset (0 to 1, where 1 = full sweep)
        
    Returns:
        Tuple of (signal_array, new_phase_offset)
    """
    duration = num_samples / sample_rate
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Calculate sweep rate (Hz/s)
    sweep_rate = bandwidth / sweep_time
    
    # Calculate phase within sweep cycle
    phase = (phase_offset + t / sweep_time) % 1.0
    
    # Linear frequency sweep: f(t) = f_min + (f_max - f_min) * phase
    f_min = center_freq - bandwidth / 2
    f_max = center_freq + bandwidth / 2
    
    # Instantaneous frequency
    inst_freq = f_min + (f_max - f_min) * phase
    
    # Generate chirp signal using instantaneous phase
    # Phase is integral of frequency: φ(t) = 2π ∫ f(t) dt
    inst_phase = 2 * np.pi * (f_min * t + (f_max - f_min) * sweep_time * (phase**2) / 2)
    
    # Generate signal
    signal = amplitude * np.sin(inst_phase)
    
    # Calculate new phase offset for next iteration
    new_phase_offset = (phase_offset + duration / sweep_time) % 1.0
    
    return signal.astype(np.uint16), new_phase_offset


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
    """Main simulation loop with FMCW radar simulation."""
    global _fmcw_phase
    
    # Ensure output directory exists
    output_path = Path(FILENAME)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🎯 RF Data Simulator - FMCW Radar Mode")
    print("=" * 60)
    print(f"Output file: {FILENAME}")
    print(f"Update rate: {1/UPDATE_INTERVAL:.1f} Hz")
    print()
    print("📡 Signal Configuration:")
    print(f"  CH1: {CH1_BASE_FREQ/1e6:.1f} MHz ± {CH1_JITTER/1e3:.1f} kHz (baseline)")
    print(f"  CH2: {CH2_BASE_FREQ/1e6:.1f} MHz ± {CH2_BANDWIDTH/1e6:.1f} MHz (FMCW sweep)")
    print(f"  FMCW Sweep: {CH2_BANDWIDTH/1e6:.1f} MHz in {CH2_SWEEP_TIME*1000:.1f} ms")
    print(f"  Sweep Rate: {1/CH2_SWEEP_TIME:.0f} Hz")
    print()
    print("Press Ctrl+C to stop.\n")

    try:
        iteration = 0
        while True:
            iteration += 1
            
            # CH1: Simple sine wave with jitter (low frequency baseline)
            freq1 = CH1_BASE_FREQ + np.random.randint(-CH1_JITTER, CH1_JITTER + 1)
            signal1 = generate_signal(freq1, CH1_AMPLITUDE, BUFFER_SAMPLES, SAMPLE_RATE)
            
            # CH2: FMCW chirp signal (>10 MHz for target detection)
            signal2, _fmcw_phase = generate_fmcw_signal(
                center_freq=CH2_BASE_FREQ,
                bandwidth=CH2_BANDWIDTH,
                sweep_time=CH2_SWEEP_TIME,
                amplitude=CH2_AMPLITUDE,
                num_samples=BUFFER_SAMPLES,
                sample_rate=SAMPLE_RATE,
                phase_offset=_fmcw_phase
            )
            
            # Interleave data (same format as real hardware)
            interleaved_data = create_interleaved_data(signal1, signal2)

            # Write to binary file
            with open(FILENAME, "wb") as f:
                f.write(struct.pack(f'<{len(interleaved_data)}H', *interleaved_data))
            
            # Calculate current FMCW frequency range
            f_min = (CH2_BASE_FREQ - CH2_BANDWIDTH / 2) / 1e6
            f_max = (CH2_BASE_FREQ + CH2_BANDWIDTH / 2) / 1e6
            
            # Print status every 20 iterations (~1 second)
            if iteration % 20 == 0:
                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"CH1: {freq1/1000:.1f} kHz | "
                    f"CH2: {f_min:.1f}-{f_max:.1f} MHz (FMCW) | "
                    f"Phase: {_fmcw_phase*100:.1f}%"
                )
            
            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("✅ Simulation stopped.")
        print(f"📊 Total iterations: {iteration}")
        print(f"⏱️  Total time: {iteration * UPDATE_INTERVAL:.1f} seconds")
        print("=" * 60)


if __name__ == "__main__":
    main()