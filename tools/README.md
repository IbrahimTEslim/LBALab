# NTFS Forensics Tools

This directory contains the core toolkit implementations.

## Tools Overview

### ntfs_forensics_toolkit.py
**Main unified toolkit** - Comprehensive NTFS forensics analysis tool combining all functionality:
- File-to-LBA mapping with extent analysis
- MFT record reading and parsing
- File residency detection
- Direct LBA operations
- Interactive and command-line interfaces

### 01_lba_reader.py
**LBA Content Reader** - Direct sector reading and analysis:
- Read raw data from specific Logical Block Addresses
- Detect and analyze MFT records in raw data
- File type identification by signature
- Hex dump visualization

### 02_file_to_lba_mapper.py
**File-to-LBA Mapper** - Maps files to physical disk locations:
- VCN → LCN → LBA mapping for files
- File extent allocation and fragmentation analysis
- Sparse file detection
- Cluster allocation visualization

### 04_residency_checker.py
**Residency Checker** - File storage method detection:
- Determine if files are resident or non-resident
- Uses cluster allocation method for accuracy
- No admin privileges required for basic checks
- Detailed file information display

## Usage

Each tool can be run independently:

```bash
# Run unified toolkit
python ntfs_forensics_toolkit.py

# Run individual tools
python 01_lba_reader.py
python 02_file_to_lba_mapper.py
python 04_residency_checker.py
```

## Requirements

- Windows operating system
- Python 3.6+
- Administrator privileges (for low-level disk access)

## Safety

All tools perform low-level disk operations. Use with caution and proper backups.