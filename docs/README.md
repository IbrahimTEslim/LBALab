# NTFS Forensics Toolkit

A comprehensive, open-source toolkit for NTFS file system forensics and low-level disk analysis. This toolkit combines multiple NTFS analysis capabilities into a single, well-structured application for forensic investigators, system administrators, and security researchers.

## 🚀 Features

- **File to LBA Mapping**: Convert file locations to Logical Block Addresses (VCN → LCN → LBA)
- **MFT Record Analysis**: Extract and analyze Master File Table records with detailed parsing
- **File Residency Detection**: Determine if files are resident (stored in MFT) or non-resident
- **Direct LBA Operations**: Read and write data directly to/from disk sectors
- **Partition Analysis**: Analyze partition information and structure
- **NTFS Volume Analysis**: Examine NTFS volume structure and metadata
- **File Extent Mapping**: Map file cluster allocation and fragmentation
- **Raw Disk Content Analysis**: Analyze raw disk content with file type detection
- **Named Stream Detection**: Identify and analyze NTFS alternate data streams
- **Comprehensive MFT Parsing**: Deep analysis of MFT record structure and attributes
- **Step-by-step LBA Calculations**: Detailed breakdown of address calculations

## 📋 Requirements

- Windows operating system
- Python 3.6 or higher
- Administrator privileges (for low-level disk access)

## 🔧 Installation

1. Clone or download this repository
2. No additional dependencies required (uses only Python standard library and Windows API)

## 💻 Usage

### Main Unified Tool

**`ntfs_forensics_toolkit.py`** - The complete, comprehensive NTFS forensics toolkit

#### Command Line Interface

```bash
# Analyze a file and show its complete LBA mapping
python ntfs_forensics_toolkit.py --analyze-file "C:\Windows\notepad.exe"

# Read data from a specific LBA with automatic MFT detection
python ntfs_forensics_toolkit.py --read-lba 0:2048

# Check if a file is resident or non-resident
python ntfs_forensics_toolkit.py --check-residency "C:\small_file.txt"

# Analyze specific MFT record with hex dump
python ntfs_forensics_toolkit.py --mft-record C:5 --hex

# Interactive mode with full menu
python ntfs_forensics_toolkit.py
```

#### Interactive Mode

Run the toolkit without arguments to enter interactive mode:

```bash
python ntfs_forensics_toolkit.py
```

This provides a comprehensive menu-driven interface with:
1. **File Analysis** - Complete NTFS file analysis with extent mapping
2. **LBA Reading** - Direct sector reading with MFT record detection
3. **Residency Checking** - Determine file storage method
4. **MFT Record Analysis** - Deep MFT record parsing and analysis

### Individual Specialized Tools

#### `01_lba_reader.py`
**Purpose**: Direct LBA content reading and analysis
- Reads raw data from specific Logical Block Addresses
- Detects and analyzes MFT records
- Identifies file types by signature
- Provides hex dump visualization

#### `02_file_to_lba_mapper.py`
**Purpose**: Maps files to their physical disk locations
- Shows VCN → LCN → LBA mapping for files
- Analyzes file extent allocation and fragmentation
- Detects sparse files and compression

#### `04_residency_checker.py`
**Purpose**: File residency detection
- Determines if files are resident or non-resident
- Uses cluster allocation method for accuracy
- No admin privileges required
- Provides detailed file information

## 🔍 Key Capabilities

### Comprehensive File Analysis
- **Complete VCN → LCN → LBA mapping** with detailed extent information
- **MFT record location calculation** with step-by-step breakdown
- **File fragmentation analysis** showing all extents and their locations
- **Named stream detection** for files with alternate data streams
- **Residency determination** using multiple detection methods

### Advanced MFT Analysis
- **Direct MFT record reading** from any record number
- **Detailed attribute parsing** including $DATA attributes
- **Hex dump visualization** of raw MFT record data
- **Signature validation** and record status checking
- **Named stream enumeration** within MFT records

### Low-Level Disk Operations
- **Direct LBA reading** with automatic content analysis
- **MFT record detection** in raw disk data
- **File type identification** by signature analysis
- **Partition information** retrieval and analysis

## 📊 Example Output

### File Analysis Example
```
================================================================================
NTFS Analysis for: C:\Windows\System32\notepad.exe
================================================================================
Type: File
Size: 179,712 bytes
Drive: C:

=== MFT Record Information ===
MFT Record Number: 87,234
Sequence Number: 3
MFT Record LBA (relative): 1,245,678
MFT Record LBA (absolute): 2,293,890

=== File Data Status ===
Status: NON-RESIDENT (file data stored in clusters on disk)

=== File Data Extents (VCN → LCN → LBA) ===
Extent 1: VCN 0-43 (44 clusters, 180,224 bytes)
           → LCN 234,567 → LBA 2,110,234 → Byte offset 1,080,439,808

Total clusters: 44
Allocated clusters: 44
Sparse clusters: 0
Total allocated size: 180,224 bytes

=== MFT Record LBA Calculation ===
1. MFT starts at LCN 786,432
2. MFT byte offset = 786,432 × 4,096 = 3,221,225,472
3. Record 87,234 offset = 87,234 × 1,024 = 89,327,616
4. Total offset = 3,221,225,472 + 89,327,616 = 3,310,553,088
5. Relative LBA = 3,310,553,088 ÷ 512 = 6,466,517
6. Absolute LBA = 2,048 + 6,466,517 = 6,468,565
```

## ⚠️ Safety Notice

**CRITICAL WARNINGS**: This toolkit performs low-level disk operations that can potentially damage your system if used incorrectly. Always:

### Before Using:
- **Create full system backups** before any analysis
- **Test on non-production systems** or virtual machines first
- **Understand the implications** of each operation before execution
- **Run as Administrator only when necessary** for specific operations

### During Analysis:
- **Use read-only operations** whenever possible
- **Verify write operations** multiple times before execution
- **Monitor system resources** during intensive operations
- **Stop immediately** if unexpected behavior occurs

### Understanding Risks:
- **MFT Corruption**: Improper MFT access can render the file system unbootable
- **Data Loss**: Direct LBA writes can overwrite critical system data
- **System Instability**: Low-level disk access may cause system crashes
- **File System Damage**: Incorrect operations can corrupt NTFS structures

### Recommended Practices:
- Always work with **disk images** rather than live systems when possible
- Use **write-blocking hardware** for forensic analysis
- Maintain **detailed logs** of all operations performed
- Have **recovery procedures** ready before starting analysis

### Legal and Ethical Considerations:
- Ensure you have **proper authorization** before analyzing any system
- Follow **chain of custody** procedures for forensic evidence
- Comply with **local laws and regulations** regarding digital forensics
- Respect **privacy and confidentiality** of analyzed data

## 🎓 Educational Purpose

This toolkit is designed for:
- **Digital Forensics Training**: Understanding NTFS internals and file system forensics
- **System Administration**: Analyzing disk layout and file allocation patterns
- **Security Research**: Low-level disk analysis techniques and methodologies
- **File System Development**: Learning NTFS structure and behavior in detail

## 🔬 Technical Details

### Understanding NTFS File References

NTFS uses a sophisticated file reference system to ensure data integrity and security:

```
File Reference = MFT Record Number (48 bits) + Sequence Number (16 bits)
```

**Example Scenario:**
1. File "document.txt" created → MFT record 1234, sequence 1
2. File deleted → MFT record 1234 marked as free
3. New file "photo.jpg" created → MFT record 1234, sequence 2 (incremented)
4. Old handle to "document.txt" (seq 1) → Access denied due to sequence mismatch

This prevents security vulnerabilities where old file handles could accidentally access new files.

### File Storage Decision Tree

```
File Size < ~700 bytes?
├─ YES → Store as RESIDENT in MFT record
│         ├─ Faster access (no disk seeks)
│         ├─ No fragmentation possible
│         └─ Common for registry, small config files
└─ NO  → Store as NON-RESIDENT in clusters
          ├─ Uses extent mapping (VCN→LCN→LBA)
          ├─ Can be fragmented across disk
          ├─ Supports compression/encryption
          └─ Allows sparse allocation
```

### Address Translation Process

```
1. Application requests file offset 8192
2. NTFS calculates VCN: 8192 ÷ 4096 = VCN 2
3. Extent map lookup: VCN 2 → LCN 50000
4. Calculate LBA: Partition_Start + (LCN × Sectors_Per_Cluster)
5. Physical read: LBA × 512 = byte offset on disk
```

### MFT Record Lifecycle

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   FREE      │───▶│   ALLOCATED  │───▶│   IN_USE    │
│ (seq = n)   │    │  (seq = n)   │    │ (seq = n)   │
└─────────────┘    └──────────────┘    └─────────────┘
       ▲                                       │
       │            ┌──────────────┐          │
       └────────────│   DELETED    │◀─────────┘
                    │ (seq = n+1)  │
                    └──────────────┘
```

### Forensic Analysis Workflow

1. **File System Validation**
   - Verify NTFS boot sector signature
   - Validate MFT location and structure
   - Check volume geometry consistency

2. **MFT Record Analysis**
   - Parse record header and validate signature
   - Check sequence number consistency
   - Analyze attribute structure and residency

3. **Data Recovery Techniques**
   - Scan free MFT records for deleted files
   - Analyze unallocated clusters for file fragments
   - Reconstruct fragmented files using extent maps

4. **Timeline Reconstruction**
   - Extract creation, modification, access timestamps
   - Correlate file system events
   - Identify suspicious activity patterns

### NTFS Concepts Covered

#### Core NTFS Structures
- **Virtual Cluster Numbers (VCN)**: Logical cluster numbering within a file (0, 1, 2, ...)
- **Logical Cluster Numbers (LCN)**: Physical cluster numbers on the NTFS volume
- **Logical Block Addresses (LBA)**: Physical sector addresses on the disk
- **Master File Table (MFT)**: NTFS metadata structure containing file records
- **File Residency**: Small files stored within MFT records vs. separate clusters
- **Data Runs**: Compression method for storing extent information
- **Named Streams**: NTFS alternate data streams attached to files
- **Sparse Files**: Files with unallocated regions (holes)

#### MFT Record Structure
- **MFT Record Number**: Unique identifier for each file/directory (48-bit)
- **Sequence Number**: 16-bit counter preventing stale file references
  - Incremented when MFT record is reused for different file
  - Prevents "use after free" scenarios in file system
  - Part of file index: `File Index = MFT Record Number + Sequence Number`
  - **Security Feature**: Old file handles can't access new files in recycled MFT slots
- **File Index**: 64-bit unique file identifier combining MFT record number and sequence
- **Link Count**: Number of hard links pointing to this file
- **Flags**: Record status (IN_USE, DIRECTORY, etc.)

#### File Storage Methods
- **Resident Files**: Data stored directly in MFT record (typically < 700 bytes)
  - Faster access, no fragmentation
  - Common for small files, registry entries, metadata
- **Non-Resident Files**: Data stored in separate disk clusters
  - Uses extent mapping (VCN → LCN → LBA)
  - Can be fragmented across multiple extents
  - Supports compression, encryption, sparse allocation

#### NTFS Attributes
- **$STANDARD_INFORMATION (0x10)**: Timestamps, file attributes
- **$FILE_NAME (0x30)**: Filename and directory information
- **$DATA (0x80)**: File content (can have multiple named streams)
- **$INDEX_ROOT (0x90)**: Directory index structure
- **$BITMAP (0xB0)**: Cluster allocation bitmap
- **Attribute Residency**: Attributes can be resident or non-resident

#### Advanced NTFS Features
- **Alternate Data Streams (ADS)**: Additional $DATA attributes with names
  - Hidden from normal file operations
  - Used by applications for metadata storage
  - Security concern: can hide malicious content
- **File Compression**: NTFS-level compression using data runs
- **Sparse Files**: Files with "holes" (unallocated regions)
  - VCN ranges marked as sparse (LCN = -1)
  - Saves disk space for large files with empty sections
- **Hard Links**: Multiple directory entries pointing to same MFT record
  - Share same file data and metadata
  - Link count tracks number of references

#### Disk Geometry and Addressing
- **Sectors**: Smallest addressable unit (typically 512 bytes)
- **Clusters**: NTFS allocation unit (multiple sectors, typically 4KB)
- **Partition Layout**: MBR/GPT partition table, partition starting LBA
- **Volume Structure**: Boot sector, MFT location, cluster allocation
- **Address Translation**: File offset → VCN → LCN → LBA → Physical sector

#### Forensic Indicators
- **Signature Validation**: "FILE" signature in MFT records
- **Record Status**: IN_USE vs FREE vs BAAD (corrupted)
- **Sequence Mismatch**: Indicates file deletion/recreation
- **Timestamp Analysis**: Creation, modification, access times
- **Deleted File Recovery**: Analyzing free MFT records and unallocated clusters
- **File Carving**: Recovering files from raw disk data using signatures

### Windows API Usage

The toolkit demonstrates proper usage of:
- `CreateFileW()` for opening files, volumes, and physical drives
- `DeviceIoControl()` for FSCTL operations and disk queries
- `GetFileInformationByHandle()` for file metadata extraction
- `FSCTL_GET_RETRIEVAL_POINTERS` for extent mapping
- `FSCTL_GET_NTFS_VOLUME_DATA` for volume information
- Low-level file positioning and reading operations

## 🏗️ Architecture

### Class Structure
- **`NTFSForensicsToolkit`**: Main toolkit class with all functionality
- **`WindowsStructures`**: Windows API structure definitions
- **`NTFSForensicsError`**: Custom exception handling

### Key Methods
- `print_file_analysis()`: Comprehensive file analysis with detailed output
- `analyze_mft_record()`: Direct MFT record analysis by number
- `parse_mft_attributes()`: Deep MFT attribute parsing
- `get_file_extents()`: VCN → LCN mapping extraction
- `read_mft_record()`: Direct MFT record reading from disk
- `is_file_resident()`: Accurate residency detection

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## ⚠️ Disclaimer

This software is provided for educational and research purposes only. Users are responsible for complying with all applicable laws and regulations. The authors are not responsible for any misuse or damage caused by this software.

## 📞 Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Review the comprehensive code documentation
- Check the examples in the toolkit
- Refer to the technical documentation

---

**Version**: 2.0.0  
**Author**: NTFS Forensics Lab  
**Last Updated**: 2024

### 🆕 Version 2.0.0 Updates
- **Complete MFT record analysis** with attribute parsing
- **Named stream detection** and analysis
- **Enhanced file extent mapping** with detailed calculations
- **Step-by-step LBA calculations** for educational purposes
- **Improved error handling** and user feedback
- **Comprehensive hex dump visualization**
- **Advanced MFT record parsing** with debug capabilities
- **Professional command-line interface** with multiple options
- **Interactive mode enhancements** with MFT record analysis