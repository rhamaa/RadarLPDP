#!/usr/bin/env python3
"""
RF Analytics Dashboard Launcher
===============================
Script untuk menjalankan dashboard analytics
"""

import sys
import os
from pathlib import Path

def check_dependencies():
    """Check required dependencies"""
    required_packages = [
        'panel', 'numpy', 'scipy', 'matplotlib', 
        'pandas', 'param', 'holoviews', 'bokeh'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\n🔧 Install missing packages with:")
        print("   pip install -r requirements_analytics.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def check_data_file():
    """Check if live data file exists"""
    live_file = Path("live/live_acquisition_ui.bin")
    
    if not live_file.exists():
        print("⚠️  Live data file not found:")
        print(f"   {live_file.absolute()}")
        print("\n💡 Solutions:")
        print("   1. Run your C acquisition program first")
        print("   2. Or create test data with create_test_data()")
        return False
    
    print(f"✅ Data file found: {live_file}")
    return True

def create_test_data():
    """Create test data for development"""
    import numpy as np
    
    # Create live directory if not exists
    os.makedirs("live", exist_ok=True)
    
    # Generate test RF signal
    sample_rate = 20_000_000
    duration = 8192 / sample_rate  # Duration matching buffer size
    t = np.linspace(0, duration, 8192)
    
    # Test signals
    freq1 = 1e6  # 1 MHz sine wave for CH1
    freq2 = 2e6  # 2 MHz sine wave for CH3
    
    ch1_signal = 0.5 * np.sin(2 * np.pi * freq1 * t) + 0.1 * np.random.randn(len(t))
    ch2_signal = 0.3 * np.sin(2 * np.pi * freq2 * t) + 0.1 * np.random.randn(len(t))
    
    # Convert to uint16 (simulate ADC output)
    ch1_uint16 = ((ch1_signal + 10) * 65535 / 20).astype(np.uint16)
    ch2_uint16 = ((ch2_signal + 10) * 65535 / 20).astype(np.uint16)
    
    # Interleave data [CH1_0, CH3_0, CH1_1, CH3_1, ...]
    interleaved = np.empty(len(ch1_uint16) * 2, dtype=np.uint16)
    interleaved[0::2] = ch1_uint16
    interleaved[1::2] = ch2_uint16
    
    # Save to binary file
    with open("live/live_acquisition_ui.bin", "wb") as f:
        f.write(interleaved.tobytes())
    
    print("✅ Test data created: live/live_acquisition_ui.bin")
    print(f"   - Duration: {duration*1000:.2f} ms")
    print(f"   - CH1: {freq1/1e6:.1f} MHz sine wave")
    print(f"   - CH3: {freq2/1e6:.1f} MHz sine wave")

def main():
    """Main launcher function"""
    print("🚀 RF Analytics Dashboard Launcher")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Check data file
    data_available = check_data_file()
    
    if not data_available:
        response = input("\n❓ Create test data for development? (y/n): ")
        if response.lower() == 'y':
            create_test_data()
        else:
            print("⏹️  Exiting - no data available")
            return 1
    
    # Launch dashboard
    print("\n🌐 Starting RF Analytics Dashboard...")
    print("📍 Dashboard will be available at: http://localhost:5007")
    print("⏹️  Press Ctrl+C to stop the server")
    
    try:
        from analytics import create_dashboard
        dashboard = create_dashboard()
        dashboard.show(port=5007, autoreload=True)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
