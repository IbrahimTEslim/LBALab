# NTFS Forensics Lab - File Organization Summary

This document provides an overview of the reorganized NTFS forensics tools with their new names and purposes.

## Main Unified Tool

### `ntfs_forensics_toolkit.py`
**The complete, unified NTFS forensics toolkit that combines all functionality**
- Command-line interface with arguments
- Interactive menu-driven mode
- Comprehensive file analysis
- LBA operations
- MFT record analysis
- File residency detection
- All features from individual tools combined

## Individual Specialized Tools

### `01_lba_reader.py` 
**(Previously: r_lba.py)**
**Purpose**: Direct LBA content reading and analysis
- Reads raw data from specific Logical Block Addresses
- Detects and analyzes MFT records
- Identifies file types by signature
- Provides hex dump visualization
- Context manager for safe drive access

### `02_file_to_lba_mapper.py`
**(Previously: lba.py, f_2_lba.py, lba_all.py)**
**Purpose**: Maps files to their physical disk locations
- Shows VCN → LCN → LBA mapping for files
- Analyzes file extent allocation and fragmentation
- Calculates partition offsets
- Supports sparse files and compression

### `03_mft_analyzer.py`
**(Previously: mft.py, mft_fixed.py)**
**Purpose**: MFT record extraction and analysis
- Fetches raw MFT records from disk
- Parses MFT record structure and attributes
- Analyzes file metadata and properties
- Calculates MFT record LBA locations

### `04_residency_checker.py`
**(Previously: res.py, res2.py)**
**Purpose**: File residency detection (resident vs non-resident)
- Determines if files are stored in MFT or separate clusters
- Uses cluster allocation method for accuracy
- No administrator privileges required
- Provides detailed file information

### `05_lba_writer.py`
**(Previously: w_lba.py, lba_direct.py, lba_safe.py)**
**Purpose**: Direct LBA writing operations
- Writes data directly to disk sectors
- Includes safety checks and confirmations
- Supports different access methods
- Requires administrator privileges

### `06_partition_analyzer.py`
**(Previously: pf_lba.py)**
**Purpose**: Partition information analysis
- Retrieves partition layout information
- Calculates partition starting LBAs
- Supports both MBR and GPT partitions
- Shows partition geometry details

### `07_deep_file_writer.py`
**(Previously: deep_write.py)**
**Purpose**: Advanced file block manipulation
- Locates exact disk blocks occupied by files
- Writes data above file clusters
- Advanced cluster allocation analysis
- File extent manipulation capabilities

### `08_ntfs_volume_analyzer.py`
**(Previously: ntfs_lba_tool.py, lba_resd.py)**
**Purpose**: Comprehensive NTFS volume structure analysis
- Complete NTFS volume information
- MFT location and structure analysis
- Volume geometry and layout
- Advanced forensic capabilities

## File Naming Convention

The new naming convention follows this pattern:
- `XX_descriptive_name.py` where XX is a number indicating complexity/dependency
- Numbers 01-08 represent increasing complexity and specialization
- `ntfs_forensics_toolkit.py` is the main unified tool

## Usage Recommendations

### For Beginners:
1. Start with `ntfs_forensics_toolkit.py` (unified tool)
2. Use `04_residency_checker.py` (no admin required)
3. Try `01_lba_reader.py` for basic LBA operations

### For Advanced Users:
1. Use individual tools for specific tasks
2. `02_file_to_lba_mapper.py` for file location analysis
3. `03_mft_analyzer.py` for detailed MFT forensics
4. `05_lba_writer.py` for disk modification (use with caution)

### For Forensic Analysis:
1. `ntfs_forensics_toolkit.py` for comprehensive analysis
2. `08_ntfs_volume_analyzer.py` for volume-level investigation
3. `07_deep_file_writer.py` for advanced manipulation

## Safety Levels

### Safe (Read-only operations):
- `01_lba_reader.py`
- `02_file_to_lba_mapper.py`
- `03_mft_analyzer.py`
- `04_residency_checker.py`
- `06_partition_analyzer.py`
- `08_ntfs_volume_analyzer.py`

### Caution Required (Write operations):
- `05_lba_writer.py`
- `07_deep_file_writer.py`
- Write functions in `ntfs_forensics_toolkit.py`

## Documentation Files

### `README.md`
Complete documentation for the entire toolkit including:
- Installation instructions
- Usage examples
- Safety warnings
- Technical details
- Contributing guidelines

### `file_organization_summary.md` (this file)
Overview of all tools and their purposes

## Migration from Old Files

| Old Filename | New Filename | Status |
|--------------|--------------|---------|
| r_lba.py | 01_lba_reader.py | ✅ Renamed & Enhanced |
| lba.py | 02_file_to_lba_mapper.py | ✅ Renamed & Enhanced |
| f_2_lba.py | Merged into 02_file_to_lba_mapper.py | ✅ Consolidated |
| lba_all.py | Merged into ntfs_forensics_toolkit.py | ✅ Consolidated |
| mft.py | 03_mft_analyzer.py | ✅ Renamed & Enhanced |
| mft_fixed.py | Merged into 03_mft_analyzer.py | ✅ Consolidated |
| res.py | 04_residency_checker.py | ✅ Renamed & Enhanced |
| res2.py | Merged into 04_residency_checker.py | ✅ Consolidated |
| w_lba.py | 05_lba_writer.py | ✅ Renamed & Enhanced |
| lba_direct.py | Merged into 05_lba_writer.py | ✅ Consolidated |
| lba_safe.py | Merged into 05_lba_writer.py | ✅ Consolidated |
| pf_lba.py | 06_partition_analyzer.py | ✅ Renamed & Enhanced |
| deep_write.py | 07_deep_file_writer.py | ✅ Renamed & Enhanced |
| ntfs_lba_tool.py | 08_ntfs_volume_analyzer.py | ✅ Renamed & Enhanced |
| lba_resd.py | Merged into 08_ntfs_volume_analyzer.py | ✅ Consolidated |

## Next Steps

1. **Test the unified toolkit**: `python ntfs_forensics_toolkit.py`
2. **Review documentation**: Read `README.md` for complete usage guide
3. **Try individual tools**: Start with read-only operations
4. **Contribute**: Add new features or improve existing functionality

All tools now include:
- Comprehensive docstrings explaining their purpose
- Better error handling and user feedback
- Consistent coding style and structure
- Safety warnings for write operations
- Example usage and interactive modes