# 📋 Developer Checklist - Post Refactoring

## ✅ Immediate Actions (Do Now)

### 1. Review Changes
- [ ] Read `QUICK_SUMMARY.md` for overview
- [ ] Review modified files:
  - [ ] `config.py`
  - [ ] `functions/data_processing.py`
  - [ ] `widgets/metrics.py`
  - [ ] `app/callbacks.py`
  - [ ] `app/setup.py`
  - [ ] `dumy_gen.py`
  - [ ] `analytics.py`

### 2. Test Application
- [ ] Run `python main.py` - Check UI works
- [ ] Run `python dumy_gen.py` - Check data generator
- [ ] Run `python run_analytics.py` - Check analytics dashboard
- [ ] Verify all features work as expected
- [ ] Check for any runtime errors

### 3. Understand New Structure
- [ ] Review shared functions in `data_processing.py`
- [ ] Understand type hints usage
- [ ] Check import organization (PEP 8)
- [ ] Review helper functions in `callbacks.py`

---

## 🔧 Development Guidelines (Follow These)

### When Writing New Code

#### 1. Always Use Type Hints
```python
# ✅ Good
def process_signal(
    data: np.ndarray,
    sample_rate: int,
    window: str = 'hann'
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Process signal and return results."""
    pass

# ❌ Bad
def process_signal(data, sample_rate, window='hann'):
    pass
```

#### 2. Use Shared Functions (DRY)
```python
# ✅ Good - Use existing functions
from functions.data_processing import load_and_process_data, compute_fft

ch1, ch2, n, sr = load_and_process_data(filepath, SAMPLE_RATE)
freqs, mags = compute_fft(ch1, sr)

# ❌ Bad - Don't duplicate
with open(filepath, 'rb') as f:
    data = f.read()
# ... duplicate processing code
```

#### 3. Write Docstrings
```python
# ✅ Good
def analyze_signal(data: np.ndarray) -> Dict[str, float]:
    """Analyze signal and compute metrics.
    
    Args:
        data: Input signal array
        
    Returns:
        Dictionary containing analysis metrics
    """
    pass

# ❌ Bad
def analyze_signal(data):
    # analyze signal
    pass
```

#### 4. Organize Imports (PEP 8)
```python
# ✅ Good
# Standard library
import os
from typing import Dict

# Third-party
import numpy as np
import panel as pn

# Local
from config import SAMPLE_RATE
from functions.data_processing import compute_fft

# ❌ Bad
import numpy as np
from config import SAMPLE_RATE
import os
import panel as pn
from functions.data_processing import compute_fft
```

---

## 📝 Code Review Checklist

### Before Committing Code
- [ ] All functions have type hints
- [ ] All functions have docstrings
- [ ] No duplicate code (check for existing functions)
- [ ] Imports are organized (stdlib → third-party → local)
- [ ] Code follows PEP 8 style
- [ ] No hardcoded values (use config.py)
- [ ] Error handling is proper
- [ ] Code compiles: `python -m py_compile yourfile.py`

### Before Pull Request
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No print statements (use logging)
- [ ] Type hints are correct
- [ ] Code is reviewed by peer

---

## 🚀 Quick Reference

### Common Imports
```python
# Data processing
from functions.data_processing import (
    load_and_process_data,
    compute_fft,
    find_peak_metrics,
    compute_basic_stats,
)

# Configuration
from config import (
    SAMPLE_RATE,
    BUFFER_SAMPLES,
    FILENAME,
    RADAR_MAX_RANGE,
)

# Type hints
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from numpy.typing import NDArray
```

### Common Patterns

#### Loading Data
```python
ch1, ch2, n_samples, sr = load_and_process_data(filepath, SAMPLE_RATE)
if ch1 is None:
    # Handle error
    return
```

#### Computing FFT
```python
freqs_khz, magnitude_db = compute_fft(data, SAMPLE_RATE, window='hann')
peak_freq, peak_mag = find_peak_metrics(freqs_khz, magnitude_db)
```

#### Computing Statistics
```python
stats = compute_basic_stats(data)
# stats contains: mean, std, min, max, rms
```

---

## 🐛 Troubleshooting

### Type Errors
**Problem:** IDE shows type errors
**Solution:** 
1. Check if you're using correct types
2. Import types: `from typing import Dict, List, Tuple`
3. Use `Optional[Type]` for nullable values

### Import Errors
**Problem:** Cannot import from modules
**Solution:**
1. Check if `__init__.py` exists in package
2. Verify import path is correct
3. Run from project root directory

### Duplicate Code Warning
**Problem:** Writing similar code to existing functions
**Solution:**
1. Search codebase for existing functions
2. Check `functions/data_processing.py` first
3. Reuse instead of rewrite

---

## 📚 Documentation to Read

### Essential (Read First)
1. `QUICK_SUMMARY.md` - Overview of changes
2. `REFACTORING_COMPLETE.md` - Final report

### Detailed (Read When Needed)
3. `REFACTORING_SUMMARY.md` - Phase 1 details
4. `REFACTORING_PHASE2.md` - Phase 2 details
5. `REDUNDANCY_FIX.md` - Redundancy analysis

---

## 🎯 Goals for Next Sprint

### High Priority
- [ ] Add unit tests (target: >80% coverage)
- [ ] Replace print with logging
- [ ] Add input validation

### Medium Priority
- [ ] Split analytics.py into modules
- [ ] Add configuration validation
- [ ] Create developer handbook

### Low Priority
- [ ] Add caching for performance
- [ ] Implement async data loading
- [ ] Add CI/CD pipeline

---

## 💡 Tips & Tricks

### IDE Setup
1. **Enable type checking** in your IDE
2. **Install Python extensions** (Pylance, etc.)
3. **Configure linter** (pylint, flake8)
4. **Use auto-formatter** (black, autopep8)

### Development Workflow
1. **Write type hints first** - Think about types
2. **Write docstring** - Document before implementing
3. **Check for existing code** - Don't duplicate
4. **Test as you go** - Don't wait until end

### Best Practices
1. **Keep functions small** - Single responsibility
2. **Use descriptive names** - Self-documenting
3. **Handle errors properly** - Don't hide exceptions
4. **Comment why, not what** - Code should be clear

---

## 🔗 Useful Commands

### Testing
```bash
# Compile check
python -m py_compile main.py

# Run application
python main.py

# Run data generator
python dumy_gen.py

# Run analytics
python run_analytics.py
```

### Code Quality
```bash
# Type checking (if mypy installed)
mypy main.py

# Code formatting (if black installed)
black *.py

# Import sorting (if isort installed)
isort *.py

# Linting (if pylint installed)
pylint main.py
```

---

## ✅ Final Checklist

### Before Starting New Feature
- [ ] Understand current codebase structure
- [ ] Check for existing similar functionality
- [ ] Plan to use shared functions
- [ ] Design with types in mind

### During Development
- [ ] Write type hints
- [ ] Write docstrings
- [ ] Follow PEP 8
- [ ] Use existing functions
- [ ] Test incrementally

### Before Committing
- [ ] Code compiles
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No duplicate code
- [ ] Peer reviewed

---

## 🎉 You're Ready!

Codebase sudah direfactor dan siap untuk development selanjutnya!

**Remember:**
- ✅ Use type hints
- ✅ Reuse existing functions
- ✅ Write clear documentation
- ✅ Follow PEP 8
- ✅ Test your code

**Happy Coding! 🚀**
