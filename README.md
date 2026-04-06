# NTFS Toolkit

A Python toolkit for NTFS forensics, low-level disk analysis, and education.

Read raw disk sectors, map files to physical locations, parse MFT records,
and learn how NTFS works — all from your terminal with live disk data.

## Install

```bash
git clone https://github.com/IbrahimTEslim/LBALab.git
cd LBALab
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```

## Quick Start

```python
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer

ca = ComprehensiveAnalyzer()
result = ca.analyze(r"C:\Windows\notepad.exe")
print(result["mft_record_lba"]["absolute"])
print(result["is_resident"])
```

## Explorer (Interactive Terminal UI)

```bash
# Interactive menu
python -m ntfs_toolkit.explorer

# Analyze a file with cinematic effects
python -m ntfs_toolkit.explorer --analyze-file "C:\Windows\notepad.exe" --animate

# Read a raw sector
python -m ntfs_toolkit.explorer --read-lba F:0

# Analyze MFT record #5 (root directory)
python -m ntfs_toolkit.explorer --mft-record C:5
```

## Learning Lab

Interactive lessons that teach NTFS internals using your actual disk:

```bash
# Interactive lesson menu
python -m ntfs_toolkit.learn --drive F --animate

# Run a specific lesson
python -m ntfs_toolkit.learn --lesson 1 --drive F

# Run all lessons
python -m ntfs_toolkit.learn --all --drive F
```

**Lessons:**
1. What is an LBA? — sectors, boot sector, NTFS signature
2. NTFS Volume Structure — partitions, clusters, geometry
3. MFT Records — header, attributes, system records
4. File Residency — resident vs non-resident storage
5. Extent Mapping — VCN → LCN → LBA address translation
6. Deleted Files — what deletion does, recovery, secure wipe

## Package Structure

```
ntfs_toolkit/
├── core/              # Low-level disk I/O and NTFS structures
│   ├── disk_io.py         # Read operations, handle management
│   ├── disk_writer.py     # Write operations (opt-in)
│   ├── ntfs_structures.py # ctypes definitions for NTFS
│   ├── windows_api.py     # Win32 constants and helpers
│   └── privileges.py      # Token privilege management
├── analyzers/         # Read-only analysis modules
│   ├── lba_reader.py          # Raw sector reading + hex dump
│   ├── file_analyzer.py       # File metadata, volume geometry
│   ├── extent_mapper.py       # VCN → LCN → LBA mapping
│   ├── mft_parser.py          # MFT record reading and parsing
│   ├── residency_checker.py   # Resident vs non-resident detection
│   └── comprehensive_analyzer.py  # All-in-one analysis
├── dangerous/         # Write operations (explicit opt-in)
│   ├── lba_writer.py          # Raw sector writing with confirmation
│   ├── content_overwriter.py  # Multi-pass data destruction
│   ├── mft_destroyer.py       # MFT record corruption
│   ├── metadata_wiper.py      # Journal and log wiping
│   ├── reference_eliminator.py # Directory and link cleanup
│   ├── ssd_handler.py         # SSD detection, TRIM, drive fill
│   └── secure_deleter.py      # Multi-phase deletion coordinator
├── explorer/          # Interactive terminal UI
│   ├── display.py     # Rich panels, tables, formatted output
│   ├── animate.py     # Cinematic effects (configurable speed)
│   └── cli.py         # Menu and argument parsing
└── learn/             # Educational lessons
    ├── lesson_lba.py        # Lesson 1: LBA and boot sectors
    ├── lesson_volume.py     # Lesson 2: Volume structure
    ├── lesson_mft.py        # Lesson 3: MFT records
    ├── lesson_residency.py  # Lesson 4: File residency
    ├── lesson_extents.py    # Lesson 5: Extent mapping
    ├── lesson_deletion.py   # Lesson 6: File deletion
    └── runner.py            # Lesson menu and CLI
```

## For Developers

```python
# Read-only analysis (safe)
from ntfs_toolkit.analyzers import LBAReader, FileAnalyzer, ExtentMapper

# Write operations (dangerous — explicit import)
from ntfs_toolkit.dangerous import LBAWriter, SecureDeleter

# Shared disk I/O instance
from ntfs_toolkit.core import DiskIO
dio = DiskIO()
reader = LBAReader(dio)
analyzer = FileAnalyzer(dio)
```

## Requirements

- Windows (uses Win32 API for disk access)
- Python 3.8+
- Administrator privileges for disk operations
- `rich` library for terminal UI

## Safety

- Read operations are safe and available by default
- Write operations require explicit import from `ntfs_toolkit.dangerous`
- Write operations include confirmation prompts
- The `DiskWriter` class is separate from `DiskIO` (read-only)

## License

MIT
