# NTFS Toolkit

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

A Python toolkit for NTFS forensics, low-level disk analysis, and education.

Read raw disk sectors, map files to physical locations, parse MFT records,
and learn how NTFS works — all from your terminal with live disk data.

---

## Table of Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Explorer (Interactive Terminal UI)](#explorer)
- [Learning Lab](#learning-lab)
- [Python API Reference](#python-api-reference)
- [CLI Reference](#cli-reference)
- [Package Structure](#package-structure)
- [Configuration](#configuration)
- [Safety & Permissions](#safety--permissions)
- [License](#license)

---

## Install

```bash
git clone https://github.com/IbrahimTEslim/LBALab.git
cd LBALab
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

pip install -r requirements.txt
```

Or install as a package (editable mode for development):

```bash
pip install -e .
```

After installing as a package, two commands become available:

```bash
ntfs-toolkit          # launches the interactive explorer
ntfs-learn            # launches the learning lab
```

### Requirements

- **Windows** (uses Win32 API — `CreateFileW`, `DeviceIoControl`, etc.)
- **Python 3.8+**
- **Administrator privileges** for raw disk access
- **rich** library (installed automatically via requirements.txt)

---

## Quick Start

```python
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer

ca = ComprehensiveAnalyzer()
result = ca.analyze(r"C:\Windows\notepad.exe")

print(result["mft_record_lba"]["absolute"])   # physical sector address
print(result["is_resident"])                   # True if data is in MFT
print(result["file_info"]["mft_record_number"])  # MFT record index
print(result["volume_info"]["bytes_per_cluster"])  # cluster size
```

---

## Explorer

The explorer is an interactive terminal UI with rich panels, tables, and
optional cinematic animation effects.

### Interactive Mode

```bash
python -m ntfs_toolkit.explorer
python -m ntfs_toolkit.explorer --animate    # with visual effects
```

This opens a menu:

```
┌─ Options ──────────────────────────────────────────┐
│  1 │ Analyze file         — full NTFS layout       │
│  2 │ Read LBA             — hex dump of any sector  │
│  3 │ Check residency      — resident vs non-resident│
│  4 │ Analyze MFT record   — parse by record number  │
│  q │ Quit                                           │
└────────────────────────────────────────────────────┘
```

### Command-Line Mode

```bash
# Analyze a file — shows MFT record, extents, LBA calculation
python -m ntfs_toolkit.explorer --analyze-file "C:\Windows\notepad.exe"

# Same with cinematic effects (panels build line-by-line, hex streams in)
python -m ntfs_toolkit.explorer --analyze-file "C:\Windows\notepad.exe" --animate

# Read raw sector — hex dump of LBA 0 on volume F:
python -m ntfs_toolkit.explorer --read-lba F:0

# Read from physical drive — LBA 2048 on PhysicalDrive0
python -m ntfs_toolkit.explorer --read-lba 0:2048

# Check if a file is resident (data inside MFT) or non-resident
python -m ntfs_toolkit.explorer --check-residency "C:\Windows\win.ini"

# Parse MFT record #5 (root directory) on drive C:
python -m ntfs_toolkit.explorer --mft-record C:5
```

### Explorer Flags

| Flag | Description |
|------|-------------|
| `--analyze-file PATH` | Full NTFS analysis of a file or directory |
| `--read-lba DRIVE:LBA` | Read and hex-dump a sector. `DRIVE` is a letter (C) or number (0 for PhysicalDrive0) |
| `--check-residency PATH` | Check if file data is stored inside the MFT record |
| `--mft-record DRIVE:NUM` | Parse a specific MFT record by number |
| `--animate` | Enable cinematic visual effects (typewriter, decode, scan, hex stream) |

---

## Learning Lab

Interactive lessons that teach NTFS internals using your actual disk —
not textbook diagrams, real bytes from your drive.

### Run Lessons

```bash
# Interactive lesson menu
python -m ntfs_toolkit.learn --drive F

# With cinematic effects
python -m ntfs_toolkit.learn --drive F --animate

# Run a specific lesson (1-6)
python -m ntfs_toolkit.learn --lesson 1 --drive F

# Run all lessons sequentially
python -m ntfs_toolkit.learn --all --drive F
```

### Lessons

| # | Title | What You Learn |
|---|-------|----------------|
| 1 | **What is an LBA?** | Sectors, physical addressing, boot sector parsing, NTFS signature |
| 2 | **NTFS Volume Structure** | Partition layout, clusters vs sectors, volume geometry, partition offsets |
| 3 | **MFT Records** | Record header, FILE signature, flags, attributes, system records 0-11 |
| 4 | **File Residency** | Resident vs non-resident storage, threshold, forensic implications |
| 5 | **Extent Mapping** | VCN → LCN → LBA translation, run lists, fragmentation |
| 6 | **Deleted Files** | What deletion does/doesn't do, recovery methods, why secure wipe is hard |

### Learning Lab Flags

| Flag | Description |
|------|-------------|
| `--lesson N` | Run lesson N (1-6) |
| `--drive LETTER` | Drive letter to analyze (default: C) |
| `--animate` | Enable cinematic effects |
| `--all` | Run all 6 lessons sequentially |

---

## Python API Reference

### Analyzers (Read-Only, Safe)

```python
from ntfs_toolkit.analyzers import (
    LBAReader,
    FileAnalyzer,
    ExtentMapper,
    MFTParser,
    ResidencyChecker,
    ComprehensiveAnalyzer,
)
```

#### LBAReader

Read raw sectors from physical drives or volumes.

```python
reader = LBAReader()

# Read 512 bytes from volume C: at sector 0 (boot sector)
data = reader.read_volume("C", lba=0, size=512)

# Read from physical drive 0 at absolute LBA 2048
data = reader.read_physical(0, lba=2048, size=512)

# Format as hex dump
print(reader.hex_dump(data))
```

#### FileAnalyzer

Query file metadata, volume geometry, and partition layout.

```python
fa = FileAnalyzer()

# File info — MFT record number, size, attributes
info = fa.get_file_info(r"C:\Windows\notepad.exe")
print(info["mft_record_number"])  # e.g. 38291
print(info["sequence_number"])     # reuse counter
print(info["file_size"])           # in bytes

# Volume geometry — cluster size, MFT location, free space
vol = fa.get_volume_info("C")
print(vol["bytes_per_cluster"])    # e.g. 4096
print(vol["mft_start_lcn"])       # MFT starting cluster
print(vol["free_clusters"])        # available clusters

# Partition offset — where volume starts on physical disk
lba = fa.get_partition_start_lba("C")  # e.g. 2048

# Sectors per cluster
spc, bps = fa.get_sectors_per_cluster("C")  # e.g. (8, 512)
```

#### ExtentMapper

Map file data to physical disk locations.

```python
mapper = ExtentMapper()

# Get raw extents (VCN, next_VCN, LCN) — None if resident
extents = mapper.get_file_extents(r"C:\Windows\notepad.exe")

# Full mapping with LBA addresses
result = mapper.map_extents_to_lba(r"C:\Windows\notepad.exe")
print(result["is_resident"])       # False for large files
print(result["partition_lba"])     # partition start
for ext in result["extents"]:
    if ext["type"] == "allocated":
        print(f"LCN {ext['lcn']} → LBA {ext['lba_absolute']}")
        print(f"  {ext['size_bytes']} bytes at byte offset {ext['byte_offset']}")
```

#### MFTParser

Read and parse raw MFT records.

```python
parser = MFTParser()
fa = FileAnalyzer()
vol = fa.get_volume_info("C")

# Read MFT record #5 (root directory)
raw = parser.read_mft_record(
    "C", vol["mft_start_lcn"], vol["bytes_per_cluster"],
    vol["mft_record_size"], record_index=5
)

# Parse header
header = parser.parse_mft_header(raw)
print(header["signature_valid"])   # True if "FILE"
print(header["flags_description"]) # "IN_USE | DIRECTORY"
print(header["sequence_number"])

# Find $DATA attributes
attrs = parser.parse_mft_attributes(raw)
for attr in attrs:
    print(f"Resident: {attr['is_resident']}, Stream: {attr['stream_name']}")

# Hex dump
print(parser.hex_dump(raw, length=128))
```

#### ResidencyChecker

Check if a file's data is stored inside the MFT record.

```python
checker = ResidencyChecker()
is_resident = checker.is_file_resident(r"C:\Windows\win.ini")
# True = data inside MFT (small file), False = data in clusters
```

#### ComprehensiveAnalyzer

All-in-one analysis combining every analyzer.

```python
ca = ComprehensiveAnalyzer()

# Full file analysis
result = ca.analyze(r"C:\Windows\notepad.exe")
print(result["file_path"])
print(result["file_size"])
print(result["drive_letter"])
print(result["is_resident"])
print(result["mft_record_lba"]["absolute"])
print(result["volume_info"]["bytes_per_cluster"])
for ext in result["extents"] or []:
    print(ext)

# Analyze a specific MFT record
mft = ca.analyze_mft_record("C", record_number=5)
print(mft["header"]["flags_description"])
print(mft["lba_absolute"])

# Verify content — compare disk bytes with file API
ext = result["extents"][0]
check = ca.verify_content(r"C:\Windows\notepad.exe", ext)
print(check["physical_match"])  # True if LBA calculation is correct
print(check["volume_match"])
```

### Dangerous (Write Operations — Explicit Opt-In)

```python
from ntfs_toolkit.dangerous import (
    LBAWriter,
    SecureDeleter,
    ContentOverwriter,
    MFTDestroyer,
    MetadataWiper,
    ReferenceEliminator,
    SSDHandler,
)
```

#### LBAWriter

Write raw data to disk sectors with safety confirmations.

```python
writer = LBAWriter()

# Write to volume — prompts for YES confirmation
writer.write_volume("D", lba=2048, data=b"test data", confirm=True)

# Write without confirmation (dangerous!)
writer.write_volume("D", lba=2048, data=b"test data", confirm=False)

# Write to physical drive
writer.write_physical(1, lba=2048, data=b"test data")

# Aggressive mode — attempts disk offline/dismount for stubborn drives
writer = LBAWriter(enable_aggressive_write=True)
```

#### SecureDeleter

Multi-phase file destruction coordinator.

```python
deleter = SecureDeleter(enable_aggressive_mode=False)

# This will prompt for triple confirmation before proceeding
success = deleter.secure_delete_file(r"D:\secret.docx", passes=7)

# Phases executed:
# 1. Content overwriting (7 passes with different patterns)
# 2. MFT record corruption
# 3. MFT mirror destruction
# 4. Metadata journal wiping ($UsnJrnl, $LogFile)
# 5. Related record elimination (directory refs, hard links, $Secure)
# 6. Hidden space wiping (SSD only)
```

### Shared DiskIO Instance

All analyzers accept an optional `disk_io` parameter for sharing a single
connection and avoiding redundant privilege escalation:

```python
from ntfs_toolkit.core import DiskIO
from ntfs_toolkit.analyzers import LBAReader, FileAnalyzer, ExtentMapper

dio = DiskIO()                    # one instance
reader = LBAReader(dio)           # shares it
analyzer = FileAnalyzer(dio)      # shares it
mapper = ExtentMapper(dio)        # shares it
```

---

## CLI Reference

### ntfs_toolkit.explorer

```
usage: python -m ntfs_toolkit.explorer [options]

options:
  --analyze-file PATH       Analyze file and show full NTFS layout
  --read-lba DRIVE:LBA      Read and hex-dump a sector
  --check-residency PATH    Check if file is resident or non-resident
  --mft-record DRIVE:NUM    Parse MFT record by number
  --animate                 Enable cinematic visual effects
  -h, --help                Show help
```

### ntfs_toolkit.learn

```
usage: python -m ntfs_toolkit.learn [options]

options:
  --lesson N                Run specific lesson (1-6)
  --drive LETTER            Drive letter to analyze (default: C)
  --animate                 Enable cinematic visual effects
  --all                     Run all lessons sequentially
  -h, --help                Show help
```

---

## Package Structure

```
ntfs_toolkit/
├── __init__.py            # Package version and docstring
├── __main__.py            # python -m ntfs_toolkit entry point
├── core/                  # Low-level disk I/O and NTFS structures
│   ├── disk_io.py             # Read operations, handle management
│   ├── disk_writer.py         # Write operations (opt-in, extends DiskIO)
│   ├── ntfs_structures.py     # ctypes definitions for NTFS on-disk formats
│   ├── windows_api.py         # Win32 constants, IOCTL codes, helpers
│   └── privileges.py          # SeManageVolumePrivilege escalation
├── analyzers/             # Read-only analysis modules (safe)
│   ├── lba_reader.py          # Raw sector reading + hex dump formatting
│   ├── file_analyzer.py       # File metadata, volume geometry, partition info
│   ├── extent_mapper.py       # VCN → LCN → LBA mapping with full calculation
│   ├── mft_parser.py          # MFT record reading, header + attribute parsing
│   ├── residency_checker.py   # Resident vs non-resident detection
│   └── comprehensive_analyzer.py  # All-in-one analysis + content verification
├── dangerous/             # Write operations (explicit opt-in, destructive)
│   ├── lba_writer.py          # Raw sector writing with confirmation prompts
│   ├── content_overwriter.py  # Multi-pass data destruction patterns
│   ├── mft_destroyer.py       # MFT record + mirror corruption
│   ├── metadata_wiper.py      # $UsnJrnl and $LogFile wiping
│   ├── reference_eliminator.py # Directory index, hard link, $Secure cleanup
│   ├── ssd_handler.py         # SSD detection, TRIM, drive fill, hidden areas
│   └── secure_deleter.py      # Multi-phase deletion coordinator
├── explorer/              # Interactive terminal UI (requires rich)
│   ├── display.py             # Rich panels, tables, formatted output
│   ├── animate.py             # Cinematic effects (configurable speed)
│   └── cli.py                 # Interactive menu + argument parsing
└── learn/                 # Educational lessons with live disk data
    ├── lesson_lba.py          # Lesson 1: What is an LBA?
    ├── lesson_volume.py       # Lesson 2: NTFS Volume Structure
    ├── lesson_mft.py          # Lesson 3: MFT Records
    ├── lesson_residency.py    # Lesson 4: File Residency
    ├── lesson_extents.py      # Lesson 5: Extent Mapping
    ├── lesson_deletion.py     # Lesson 6: Deleted Files
    └── runner.py              # Lesson menu and CLI
```

---

## Configuration

### Animation Speed

All cinematic effects are controlled by a single value in
`ntfs_toolkit/explorer/animate.py`:

```python
EFFECT_DURATION = 0.5  # seconds per effect (0.5 = snappy, 1.0 = cinematic)
```

### Verbose Disk I/O

Enable detailed logging for disk operations:

```python
from ntfs_toolkit.core import DiskIO
dio = DiskIO(verbose=True)  # prints privilege escalation, sector detection, etc.
```

---

## Safety & Permissions

| Module | Risk Level | Requires Admin | Description |
|--------|-----------|----------------|-------------|
| `analyzers` | ✅ Safe | Yes (for raw disk reads) | Read-only analysis |
| `explorer` | ✅ Safe | Yes | Interactive UI using analyzers |
| `learn` | ✅ Safe | Yes | Educational lessons using analyzers |
| `dangerous` | ⚠️ Destructive | Yes | Raw disk writes, MFT corruption |

- **Read operations** (`DiskIO`) are safe — they cannot modify disk data
- **Write operations** (`DiskWriter`) are in a separate class that must be explicitly imported
- **LBAWriter** prompts for `YES` confirmation before every write
- **SecureDeleter** requires triple confirmation (DESTROY → path match → I_UNDERSTAND)
- The `dangerous` package name makes the risk explicit at import time

---

## License

MIT
