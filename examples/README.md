# NTFS Forensics Examples

This directory contains reference implementations and example code.

## Reference Implementations

### mft.py
**Advanced MFT Analysis** - Specialized MFT record analysis tool:
- Enhanced MFT record reading with 64-bit offset support
- Detailed MFT header parsing and validation
- Comprehensive attribute analysis
- Advanced hex dump functionality
- Built-in testing with common system files

**Key Features:**
- `fetch_mft_record_raw()` - Direct MFT record reading
- `analyze_mft_record_header()` - Detailed header analysis
- `dump_mft_record_hex()` - Enhanced hex visualization
- `test_common_files()` - Built-in functionality testing

### lba_all.py
**Original Comprehensive Analyzer** - Complete NTFS analysis implementation:
- Step-by-step LBA calculations with detailed explanations
- Comprehensive file extent mapping
- Named stream detection and analysis
- Educational output with calculation breakdowns

**Key Features:**
- Detailed calculation explanations
- Educational step-by-step output
- Comprehensive extent analysis
- Named stream enumeration

## Usage

These are reference implementations that demonstrate specific techniques:

```bash
# Run MFT analyzer
python mft.py "C:\Windows\notepad.exe"
python mft.py mft:5:C --hex

# Run original comprehensive analyzer
python lba_all.py "C:\Windows\System32\kernel32.dll"
```

## Purpose

These examples serve as:
- **Learning Resources**: Understand NTFS internals step-by-step
- **Reference Code**: See different implementation approaches
- **Testing Tools**: Verify functionality with known files
- **Development Base**: Starting point for custom tools

## Integration

Features from these examples have been integrated into the main unified toolkit in `tools/ntfs_forensics_toolkit.py`, providing the best of all implementations.