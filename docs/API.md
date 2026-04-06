# API Reference

Complete Python API documentation for `ntfs_toolkit`.

---

## Core Layer (`ntfs_toolkit.core`)

The foundation — low-level disk I/O and NTFS structure definitions.

### DiskIO

Read-only disk operations. All analyzers use this internally.

```python
from ntfs_toolkit.core import DiskIO

dio = DiskIO()                    # default: silent, read-only
dio = DiskIO(verbose=True)        # prints privilege escalation details
```

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `open_file(path)` | file path | handle (int) | Open file for reading |
| `open_volume(letter)` | drive letter | handle (int) | Open volume for reading |
| `open_physical_drive(num)` | drive number | handle (int) | Open physical drive |
| `read_lba_physical(drive, lba, size)` | drive num, LBA, bytes | `bytes` | Read from physical drive |
| `read_lba_volume(letter, lba, size)` | drive letter, LBA, bytes | `bytes` | Read from volume |
| `detect_sector_size(drive)` | drive number | `int` | Detect sector size (default 512) |
| `get_physical_drive_number(letter)` | drive letter | `int` | Map volume letter to physical drive |

### DiskWriter

Extends `DiskIO` with write capabilities. Must be explicitly imported.

```python
from ntfs_toolkit.core import DiskWriter

dw = DiskWriter()                              # standard write mode
dw = DiskWriter(enable_aggressive_write=True)  # disk offline/dismount
dw = DiskWriter(verbose=True)                  # detailed logging
```

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `write_lba_physical(drive, lba, data)` | drive num, LBA, bytes | bytes written | Write to physical drive |
| `write_lba_volume(letter, lba, data)` | drive letter, LBA, bytes | bytes written | Write to volume |
| `dismount_volume(letter)` | drive letter | `bool` | Dismount volume for raw access |
| `take_disk_offline(drive)` | drive number | `bool` | Take drive offline |

All `DiskIO` methods are also available (read operations).

### WindowsAPI

Static helper methods.

```python
from ntfs_toolkit.core import WindowsAPI

WindowsAPI.is_admin()           # True if running as Administrator
WindowsAPI.close_handle(h)      # Safely close a Win32 handle
```

### Constants

```python
from ntfs_toolkit.core import ATTR_DATA, ATTR_END, SECTOR_SIZE

ATTR_DATA   # 0x80 — $DATA attribute type
ATTR_END    # 0xFFFFFFFF — end-of-attributes marker
SECTOR_SIZE # 512 — default sector size
```

---

## Analyzers (`ntfs_toolkit.analyzers`)

Read-only analysis modules. Safe to use — cannot modify disk data.

### Return Value Formats

#### ComprehensiveAnalyzer.analyze() returns:

```python
{
    "file_path": str,
    "file_size": int,                    # bytes
    "is_directory": bool,
    "drive_letter": str,                 # e.g. "C"
    "file_info": {
        "file_index": int,               # raw 64-bit index
        "mft_record_number": int,        # bits 0-47
        "sequence_number": int,          # bits 48-63
        "volume_serial": int,
        "file_size": int,
        "attributes": int,               # Win32 file attributes
        "link_count": int,
    },
    "volume_info": {
        "partition_start_lba": int,
        "bytes_per_sector": int,
        "bytes_per_cluster": int,
        "sectors_per_cluster": int,
        "mft_start_lcn": int,
        "mft_record_size": int,
    },
    "mft_record_lba": {
        "relative": int,                 # LBA relative to volume
        "absolute": int,                 # LBA on physical disk
        "byte_offset": int,              # byte offset on volume
    },
    "is_resident": bool | None,          # None if unknown
    "extents": [                         # None if resident
        {
            "start_vcn": int,
            "next_vcn": int,
            "cluster_count": int,
            "lcn": int,                  # -1 for sparse
            "lba_relative": int,
            "lba_absolute": int,
            "byte_offset": int,
            "size_bytes": int,
            "type": "allocated" | "sparse",
        },
    ],
}
```

#### ExtentMapper.map_extents_to_lba() returns:

```python
{
    "is_resident": bool,
    "extents": [...],                    # same format as above
    "partition_lba": int,
    "sectors_per_cluster": int,
}
```

#### MFTParser.parse_mft_header() returns:

```python
{
    "signature": bytes,                  # b"FILE" or other
    "signature_valid": bool,
    "fixup_offset": int,
    "fixup_count": int,
    "lsn": int,                          # Log Sequence Number
    "sequence_number": int,
    "link_count": int,
    "attrs_offset": int,
    "flags": int,
    "flags_description": str,            # "IN_USE | DIRECTORY"
    "bytes_in_use": int,
    "bytes_allocated": int,
    "base_record": int,
    "next_attr_instance": int,
    "is_in_use": bool,
    "is_directory": bool,
}
```

---

## Dangerous (`ntfs_toolkit.dangerous`)

Write operations that modify raw disk data. Every module requires
explicit import from the `dangerous` package.

### SecureDeleter Phases

When `secure_delete_file()` is called, it executes 6 phases:

| Phase | Module | What It Does |
|-------|--------|-------------|
| 1 | ContentOverwriter | Overwrites file clusters with 7+ patterns (zeros, ones, random, etc.) |
| 2 | MFTDestroyer | Corrupts the file's MFT record with multiple patterns |
| 3 | MFTDestroyer | Finds and corrupts the MFT mirror copy |
| 4 | MetadataWiper | Wipes $UsnJrnl and $LogFile entries referencing the file |
| 5 | ReferenceEliminator | Corrupts directory index entries, hard links, $Secure |
| 6 | SSDHandler | (SSD only) Wipes hidden areas, sends TRIM |

### Overwrite Patterns

ContentOverwriter uses these patterns in sequence:

| Pass | Pattern | Purpose |
|------|---------|---------|
| 1 | `0x00` (all zeros) | Clear all bits |
| 2 | `0xFF` (all ones) | Set all bits |
| 3 | `0xAA` (10101010) | Alternating pattern A |
| 4 | `0x55` (01010101) | Alternating pattern B |
| 5 | `0x00FF` repeating | Byte-level alternation |
| 6 | `0xFF00` repeating | Inverse byte alternation |
| 7+ | `os.urandom()` | Cryptographic random |

---

## Explorer Effects

The `--animate` flag enables these cinematic effects:

| Effect | Where Used | Description |
|--------|-----------|-------------|
| `typewriter` | Titles | Text appears character by character |
| `panel_build` | Info panels | Lines appear one by one from top |
| `decode_reveal` | MFT data | Random chars settle into real values |
| `hex_reveal` | Hex dumps | Bytes stream in left-to-right |
| `scan_line` | Status text | Green highlight sweeps across |
| `flash_result` | Confirmations | Text blinks twice then stays |

All effects are controlled by `EFFECT_DURATION` in `animate.py` (default: 0.5s).
