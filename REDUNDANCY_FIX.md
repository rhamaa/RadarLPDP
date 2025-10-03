# Redundancy Fix Guide - analytics.py

## 🔴 Critical Issue: Duplicate Data Loading Code

### Problem
`analytics.py` contains a `load_binary_data()` method that duplicates functionality already in `functions/data_processing.py`.

### Current Redundancy

**File 1:** `analytics.py` (lines 82-117)
```python
def load_binary_data(self, filepath):
    """Load dan parsing data binary dari file akuisisi"""
    try:
        if not os.path.exists(filepath):
            return np.array([]), np.array([]), False
            
        with open(filepath, 'rb') as f:
            raw_data = f.read()
            
        data_array = np.frombuffer(raw_data, dtype=np.uint16)
        
        if len(data_array) < 2:
            return np.array([]), np.array([]), False
            
        # Deinterleave: CH1 (odd indices), CH2 (even indices)
        ch1_data = data_array[0::2]
        ch2_data = data_array[1::2]
        
        # Convert to voltage
        ch1_voltage = (ch1_data.astype(np.float64) - 32768) * (20.0 / 65536)
        ch2_voltage = (ch2_data.astype(np.float64) - 32768) * (20.0 / 65536)
        
        return ch1_voltage, ch2_voltage, True
        
    except Exception as e:
        print(f"Error loading data: {e}")
        return np.array([]), np.array([]), False
```

**File 2:** `functions/data_processing.py` (lines 60-109)
```python
def load_and_process_data(
    filepath: str,
    sample_rate: int
) -> Tuple[Optional[NDArray[np.float32]], Optional[NDArray[np.float32]], Optional[int], int]:
    """Load binary data file, separate channels, and remove DC offset."""
    try:
        if not os.path.exists(filepath):
            return None, None, None, sample_rate

        with open(filepath, "rb") as f:
            data = f.read()
        
        if not data:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32), 0, sample_rate

        # Ensure even byte length for uint16 unpacking
        if len(data) % 2 != 0:
            data = data[:-1]

        values = np.array(
            struct.unpack(f"<{len(data)//2}H", data),
            dtype=np.float32
        )

        # Ensure even number of samples for 2-channel deinterleaving
        if len(values) % 2 != 0:
            values = values[:-1]
            
        # Deinterleave channels: CH1 (even indices), CH2 (odd indices)
        ch1 = values[::2]
        ch2 = values[1::2]
        
        # Remove DC offset
        ch1 -= np.mean(ch1)
        ch2 -= np.mean(ch2)
        
        return ch1, ch2, len(ch1), sample_rate
        
    except Exception as e:
        print(f"Error reading or processing file {filepath}: {e}")
        return None, None, None, sample_rate
```

### Differences
1. **Voltage conversion:** `analytics.py` converts to voltage, `data_processing.py` removes DC offset
2. **Return format:** Different return signatures
3. **Error handling:** Slightly different approaches

---

## ✅ Solution: Consolidate into Single Function

### Step 1: Update `data_processing.py`

Add a new function that handles both use cases:

```python
def load_and_convert_to_voltage(
    filepath: str,
    sample_rate: int,
    voltage_range: float = 20.0,
    adc_bits: int = 16
) -> Tuple[Optional[NDArray[np.float64]], Optional[NDArray[np.float64]], bool]:
    """Load binary data and convert to voltage.
    
    Args:
        filepath: Path to binary data file
        sample_rate: Sample rate in Hz
        voltage_range: ADC voltage range (±V)
        adc_bits: ADC resolution in bits
        
    Returns:
        Tuple of (ch1_voltage, ch2_voltage, success)
    """
    ch1_data, ch2_data, n_samples, _ = load_and_process_data(filepath, sample_rate)
    
    if ch1_data is None or n_samples is None or n_samples <= 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), False
    
    # Convert to voltage (ADC PCI-9846H: ±10V range, 16-bit)
    adc_max = 2 ** adc_bits
    ch1_voltage = (ch1_data.astype(np.float64) + 32768) * (voltage_range / adc_max)
    ch2_voltage = (ch2_data.astype(np.float64) + 32768) * (voltage_range / adc_max)
    
    return ch1_voltage, ch2_voltage, True
```

### Step 2: Update `analytics.py`

Replace the `load_binary_data` method:

```python
# At the top of analytics.py, add import:
from functions.data_processing import load_and_convert_to_voltage

# In RFAnalytics class, replace load_binary_data method:
def load_binary_data(self, filepath):
    """Load and parse binary data from acquisition file.
    
    Returns:
        tuple: (ch1_data, ch2_data, success)
    """
    return load_and_convert_to_voltage(filepath, SAMPLE_RATE)
```

### Step 3: Test the Changes

```python
# Test script
from analytics import RFAnalytics

analytics = RFAnalytics()
ch1, ch2, success = analytics.load_binary_data('live/live_acquisition_ui.bin')

print(f"Success: {success}")
print(f"CH1 shape: {ch1.shape}, CH2 shape: {ch2.shape}")
print(f"CH1 range: [{ch1.min():.3f}, {ch1.max():.3f}]")
print(f"CH2 range: [{ch2.min():.3f}, {ch2.max():.3f}]")
```

---

## 📊 Impact Analysis

### Before
- **Total lines:** ~35 lines of duplicate code
- **Maintenance:** Changes need to be made in 2 places
- **Testing:** Need to test 2 implementations
- **Bugs:** Potential for inconsistencies

### After
- **Total lines:** ~10 lines (wrapper function)
- **Maintenance:** Single source of truth
- **Testing:** Test once, use everywhere
- **Bugs:** Consistent behavior guaranteed

### Code Reduction
- **Removed:** ~25 lines
- **Percentage:** ~70% reduction in data loading code

---

## 🔄 Migration Checklist

- [ ] Add `load_and_convert_to_voltage()` to `data_processing.py`
- [ ] Update `analytics.py` to use new function
- [ ] Run existing tests to ensure compatibility
- [ ] Update any documentation referencing the old method
- [ ] Remove old `load_binary_data()` implementation
- [ ] Commit changes with clear message

---

## 🧪 Testing Strategy

### Unit Tests
```python
def test_load_and_convert_to_voltage():
    """Test voltage conversion from binary data."""
    # Create test data
    test_file = "test_data.bin"
    # ... create test file
    
    ch1, ch2, success = load_and_convert_to_voltage(test_file, 20_000_000)
    
    assert success == True
    assert len(ch1) > 0
    assert len(ch2) > 0
    assert -10.0 <= ch1.min() <= 10.0  # Within ±10V range
    assert -10.0 <= ch2.max() <= 10.0
```

### Integration Tests
```python
def test_analytics_integration():
    """Test analytics.py with refactored data loading."""
    analytics = RFAnalytics()
    analytics.update_data()
    
    assert len(analytics.data_ch1) > 0
    assert len(analytics.data_ch2) > 0
```

---

## 🚀 Additional Optimizations

### 1. Caching
Consider adding caching for frequently accessed files:

```python
from functools import lru_cache

@lru_cache(maxsize=10)
def load_and_convert_to_voltage_cached(filepath, sample_rate):
    """Cached version for repeated access."""
    return load_and_convert_to_voltage(filepath, sample_rate)
```

### 2. Async Loading
For large files, consider async loading:

```python
import asyncio

async def load_and_convert_to_voltage_async(filepath, sample_rate):
    """Async version for non-blocking I/O."""
    # Implementation
    pass
```

### 3. Memory Mapping
For very large files, use memory mapping:

```python
import mmap

def load_with_mmap(filepath):
    """Memory-mapped file loading for large files."""
    # Implementation
    pass
```

---

## 📝 Commit Message Template

```
refactor: consolidate duplicate data loading code

- Remove duplicate load_binary_data() from analytics.py
- Add load_and_convert_to_voltage() to data_processing.py
- Update analytics.py to use shared function
- Reduce code duplication by ~25 lines

Benefits:
- Single source of truth for data loading
- Easier maintenance and testing
- Consistent voltage conversion across codebase

Closes #[issue-number]
```

---

## 🔗 Related Files

Files that may need updates:
- `analytics.py` - Primary change
- `functions/data_processing.py` - Add new function
- `tests/test_analytics.py` - Update tests (if exists)
- `REFACTORING_SUMMARY.md` - Update status

---

**Priority:** 🔴 High  
**Effort:** 🟢 Low (1-2 hours)  
**Risk:** 🟡 Medium (requires thorough testing)
