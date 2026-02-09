# NTFS Forensics Toolkit - Modular Architecture

## Structure

```
tools/
├── core/                          # Core components (reusable)
│   ├── windows_api.py            # Windows API wrappers
│   ├── ntfs_structures.py        # NTFS data structures
│   └── disk_io.py                # Low-level disk I/O
│
├── modules/                       # Feature modules (standalone + importable)
│   ├── lba_reader.py             # Direct LBA reading
│   ├── file_analyzer.py          # File analysis
│   ├── extent_mapper.py          # VCN→LCN→LBA mapping
│   ├── mft_parser.py             # MFT record parsing
│   └── residency_checker.py      # File residency detection
│
├── ntfs_forensics_toolkit.py     # Unified interface (imports all modules)
└── cli.py                         # Command-line interface

```

## Usage

### Standalone Modules
Each module can run independently:

```bash
# Read LBA directly
python modules/lba_reader.py 0:2048 512
python modules/lba_reader.py D:2048 512

# Check file residency
python modules/residency_checker.py "C:\file.txt"

# Analyze file
python modules/file_analyzer.py "C:\file.txt"

# Map file extents
python modules/extent_mapper.py "C:\file.txt"

# Parse MFT record
python modules/mft_parser.py C:5
```

### Unified Toolkit
Use all features together:

```bash
python ntfs_forensics_toolkit.py --analyze-file "C:\file.txt"
python ntfs_forensics_toolkit.py --read-lba 0:2048
```

### As Library
Import in your own scripts:

```python
from modules import LBAReader, FileAnalyzer, ExtentMapper

# Read LBA
reader = LBAReader()
data = reader.read_physical(0, 2048)

# Analyze file
analyzer = FileAnalyzer()
info = analyzer.analyze("C:\\file.txt")

# Map extents
mapper = ExtentMapper()
extents = mapper.get_extents("C:\\file.txt")
```

## Benefits

1. **Modularity**: Each feature is independent
2. **Reusability**: Import only what you need
3. **Maintainability**: Easy to update individual components
4. **Testability**: Test modules in isolation
5. **Flexibility**: Use standalone or combined

## Migration

The original `ntfs_forensics_toolkit.py` is preserved.
New modular version provides same functionality with better organization.
