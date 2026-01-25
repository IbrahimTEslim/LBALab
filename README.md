# NTFS Forensics Toolkit

A comprehensive, open-source toolkit for NTFS file system forensics and low-level disk analysis.

## 📁 Project Structure

```
LBALab/
├── ntfs_forensics_toolkit.py    # Main entry point
├── tools/                       # Core toolkit implementations
│   ├── ntfs_forensics_toolkit.py   # Unified comprehensive toolkit
│   ├── 01_lba_reader.py            # Direct LBA content reader
│   ├── 02_file_to_lba_mapper.py    # File-to-LBA mapping tool
│   └── 04_residency_checker.py     # File residency detection
├── docs/                        # Documentation
│   ├── README.md                   # Comprehensive documentation
│   └── file_organization_summary.md # Migration guide
├── examples/                    # Reference implementations
│   ├── mft.py                      # MFT analysis reference
│   └── lba_all.py                  # Original comprehensive analyzer
└── tests/                       # Test files (future)
```

## 🚀 Quick Start

```bash
# Run the unified toolkit
python ntfs_forensics_toolkit.py

# Analyze a file
python ntfs_forensics_toolkit.py --analyze-file "C:\Windows\notepad.exe"

# Read LBA directly
python ntfs_forensics_toolkit.py --read-lba 0:2048

# Check file residency
python ntfs_forensics_toolkit.py --check-residency "C:\small_file.txt"

# Analyze MFT record
python ntfs_forensics_toolkit.py --mft-record C:5 --hex

# Run tests
python ntfs_forensics_toolkit.py --test
```

## 📖 Documentation

See [docs/README.md](docs/README.md) for comprehensive documentation including:
- Detailed feature descriptions
- Technical NTFS concepts
- Safety guidelines
- Usage examples
- Forensic workflows

## 🔧 Individual Tools

The `tools/` directory contains specialized tools that can be run independently:

- **01_lba_reader.py**: Direct LBA reading and analysis
- **02_file_to_lba_mapper.py**: File-to-physical-location mapping
- **04_residency_checker.py**: File residency detection

## 📚 Examples

The `examples/` directory contains reference implementations:

- **mft.py**: Advanced MFT record analysis
- **lba_all.py**: Original comprehensive analyzer

## ⚠️ Safety Notice

This toolkit performs low-level disk operations. Always:
- Create backups before analysis
- Test on non-production systems
- Run with appropriate privileges
- Follow forensic best practices

See [docs/README.md](docs/README.md) for detailed safety guidelines.

## 📄 License

MIT License - See LICENSE file for details

---

**Version**: 2.0.0  
**Author**: NTFS Forensics Lab  
**Last Updated**: 2024