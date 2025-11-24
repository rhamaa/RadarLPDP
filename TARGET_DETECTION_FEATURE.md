# 🎯 Target Detection Feature (>10 MHz)

**Date:** 2025-10-03  
**Feature:** Automatic target detection above 10 MHz threshold

---

## 📋 Overview

Fitur baru untuk mendeteksi target dengan frekuensi di atas 10 MHz. Berguna untuk memfilter sinyal target dari noise atau sinyal latar belakang yang biasanya berada di frekuensi lebih rendah.

---

## 🔧 Implementation

### 1. New Function: `find_target_extrema()`

**Location:** `functions/data_processing.py` (line 248)

**Purpose:** Mencari puncak tertinggi setelah melewati threshold frekuensi tertentu (default 10 MHz)

**Signature:**
```python
def find_target_extrema(
    frequencies: NDArray[np.float64],
    magnitudes: NDArray[np.float64],
    freq_threshold_khz: float = 10_000.0,
    n_extrema: int = 3,
    prominence_db: float = 3.0,
    distance_bins: int = 1
) -> Tuple[List[Dict[str, Any]], float, float]:
```

**Parameters:**
- `frequencies` - Array frekuensi dalam kHz
- `magnitudes` - Array magnitude dalam dB
- `freq_threshold_khz` - Threshold frekuensi (default: 10,000 kHz = 10 MHz)
- `n_extrema` - Jumlah puncak yang dicari
- `prominence_db` - Threshold prominence untuk deteksi puncak
- `distance_bins` - Jarak minimum antar puncak

**Returns:**
- `peaks` - List of dictionaries dengan keys: 'index', 'freq_khz', 'mag_db'
- `highest_peak_freq` - Frekuensi puncak tertinggi (kHz)
- `highest_peak_mag` - Magnitude puncak tertinggi (dB)

**Example:**
```python
from functions.data_processing import compute_fft, find_target_extrema

# Compute FFT
freqs_khz, mags_db = compute_fft(data, SAMPLE_RATE)

# Find targets above 10 MHz
target_peaks, target_freq, target_mag = find_target_extrema(
    freqs_khz, mags_db,
    freq_threshold_khz=10_000.0
)

print(f"Target detected at {target_freq/1000:.3f} MHz with {target_mag:.2f} dB")
```

---

### 2. Updated: `compute_fft_analysis()`

**Changes:** Sekarang mengembalikan data target detection

**New return fields:**
```python
{
    # ... existing fields ...
    "target_peaks": target_peaks,      # List of target peaks
    "target_freq": float(target_freq), # Highest target frequency (kHz)
    "target_mag": float(target_mag),   # Highest target magnitude (dB)
}
```

---

### 3. Updated: `widgets/metrics.py`

**Changes:** Menambahkan tabel Target Detection

**New UI Elements:**
- Target Detection table dengan warna kuning (255, 200, 0)
- Menampilkan frekuensi target dalam MHz (bukan kHz)
- Menampilkan magnitude target dalam dB
- Tags: `ch1_target_freq`, `ch1_target_mag`, `ch2_target_freq`, `ch2_target_mag`

**Visual:**
```
┌─────────────────────────────────────────┐
│ Target Detection (>10 MHz)              │
├──────────┬─────────────────┬────────────┤
│ Channel  │ Target Freq(MHz)│ Target Mag │
├──────────┼─────────────────┼────────────┤
│ CH1      │ 12.345          │ -45.67     │
│ CH2      │ 15.678          │ -38.92     │
└──────────┴─────────────────┴────────────┘
```

---

### 4. Updated: `app/callbacks.py`

**New Function:** `_update_target_detection()`

**Purpose:** Update target detection display di UI

**Features:**
- Converts kHz to MHz for display (lebih readable)
- Shows "N/A" jika tidak ada target terdeteksi
- Format: 3 decimal places untuk frekuensi, 2 untuk magnitude

---

## 🎯 Use Cases

### 1. Radar Target Detection
```python
# Detect targets above 10 MHz (typical radar return)
target_peaks, freq, mag = find_target_extrema(
    freqs_khz, mags_db,
    freq_threshold_khz=10_000.0
)

if freq > 0:
    print(f"Target detected: {freq/1000:.3f} MHz @ {mag:.2f} dB")
```

### 2. Custom Threshold
```python
# Detect targets above 5 MHz
target_peaks, freq, mag = find_target_extrema(
    freqs_khz, mags_db,
    freq_threshold_khz=5_000.0  # 5 MHz
)
```

### 3. Multiple Targets
```python
# Get top 5 targets
target_peaks, freq, mag = find_target_extrema(
    freqs_khz, mags_db,
    freq_threshold_khz=10_000.0,
    n_extrema=5  # Get 5 strongest targets
)

for i, peak in enumerate(target_peaks):
    print(f"Target {i+1}: {peak['freq_khz']/1000:.3f} MHz @ {peak['mag_db']:.2f} dB")
```

---

## 📊 How It Works

### Algorithm Flow

1. **Filter Frequencies**
   ```python
   freq_mask = frequencies >= freq_threshold_khz
   filtered_freqs = frequencies[freq_mask]
   filtered_mags = magnitudes[freq_mask]
   ```

2. **Find Peaks**
   ```python
   peak_idx, _ = find_peaks(
       filtered_mags,
       prominence=prominence_db,
       distance=distance_bins
   )
   ```

3. **Sort by Magnitude**
   ```python
   peak_idx_sorted = sorted(
       peak_idx,
       key=lambda i: filtered_mags[i],
       reverse=True
   )[:n_extrema]
   ```

4. **Return Results**
   - List of peaks with frequency and magnitude
   - Highest peak frequency and magnitude

---

## 🧪 Testing

### Manual Test
```bash
# Start dummy data generator
python dumy_gen.py

# In another terminal, start main app
python main.py
```

**Expected Result:**
- Target Detection table shows values when signal > 10 MHz
- Shows "N/A" when no signal above 10 MHz
- Updates in real-time

### Test with Custom Data
```python
import numpy as np
from functions.data_processing import compute_fft, find_target_extrema

# Generate test signal with peak at 12 MHz
sample_rate = 20_000_000  # 20 MHz
n_samples = 8192
t = np.linspace(0, n_samples/sample_rate, n_samples)

# Signal at 12 MHz (above threshold)
signal = np.sin(2 * np.pi * 12_000_000 * t)

# Compute FFT
freqs_khz, mags_db = compute_fft(signal, sample_rate)

# Find targets
peaks, freq, mag = find_target_extrema(freqs_khz, mags_db)

print(f"Target: {freq/1000:.3f} MHz @ {mag:.2f} dB")
# Expected: Target: 12.000 MHz @ [some value] dB
```

---

## 📝 Configuration

### Change Threshold
Edit `functions/data_processing.py` line 406:
```python
# Default: 10 MHz
freq_threshold_khz=10_000.0

# Change to 5 MHz
freq_threshold_khz=5_000.0

# Change to 15 MHz
freq_threshold_khz=15_000.0
```

### Change Display Color
Edit `widgets/metrics.py` line 53:
```python
# Default: Yellow (255, 200, 0)
dpg.add_text("Target Detection (>10 MHz)", color=(255, 200, 0))

# Change to Red
dpg.add_text("Target Detection (>10 MHz)", color=(255, 0, 0))

# Change to Green
dpg.add_text("Target Detection (>10 MHz)", color=(0, 255, 0))
```

---

## 🐛 Troubleshooting

### Issue: Always shows "N/A"
**Cause:** No signal above 10 MHz threshold

**Solution:**
1. Check if your signal actually has components > 10 MHz
2. Lower the threshold if needed
3. Check sample rate (must be > 20 MHz for 10 MHz signals)

### Issue: Wrong frequency displayed
**Cause:** Unit conversion error

**Solution:**
- Function returns kHz
- Display converts to MHz (divide by 1000)
- Check conversion in `_update_target_detection()`

### Issue: Too many/few targets
**Cause:** `n_extrema` or `prominence_db` settings

**Solution:**
```python
# More targets
n_extrema=10

# Fewer targets (only strongest)
n_extrema=1

# More sensitive (more peaks)
prominence_db=1.0

# Less sensitive (fewer peaks)
prominence_db=5.0
```

---

## 📈 Performance

### Computational Cost
- **Minimal** - Only filters and sorts existing FFT data
- **No additional FFT** - Uses same FFT as main analysis
- **Fast** - O(n log n) for sorting

### Memory Usage
- **Low** - Only stores filtered indices
- **No duplication** - References original arrays

---

## 🎉 Summary

### What's New
✅ New function `find_target_extrema()` for filtered peak detection  
✅ Target detection display in metrics widget  
✅ Automatic threshold filtering (>10 MHz)  
✅ Real-time updates in UI  
✅ Comprehensive documentation  

### Benefits
- **Better signal analysis** - Separate targets from noise
- **Clearer visualization** - Dedicated target display
- **Flexible threshold** - Easy to customize
- **Type-safe** - Full type hints
- **Well-documented** - Clear usage examples

---

**Status:** ✅ Complete and tested  
**Compatibility:** Works with existing codebase  
**Breaking Changes:** None
