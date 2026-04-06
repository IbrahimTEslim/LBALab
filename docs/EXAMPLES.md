# Examples

Practical usage examples for common tasks.

---

## 1. Find Where a File Lives on Disk

```python
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer

ca = ComprehensiveAnalyzer()
result = ca.analyze(r"D:\important\database.db")

if result["is_resident"]:
    print("File data is inside the MFT record (no clusters)")
else:
    for ext in result["extents"]:
        if ext["type"] == "allocated":
            print(f"Clusters {ext['start_vcn']}-{ext['next_vcn']-1}")
            print(f"  Physical LBA: {ext['lba_absolute']}")
            print(f"  Byte offset:  {ext['byte_offset']}")
            print(f"  Size:         {ext['size_bytes']} bytes")
```

## 2. Read the NTFS Boot Sector

```python
from ntfs_toolkit.analyzers import LBAReader

reader = LBAReader()
boot = reader.read_volume("C", lba=0, size=512)

# Parse key fields
oem = boot[3:11].decode("ascii").strip()
bps = int.from_bytes(boot[11:13], "little")
spc = boot[13]
mft_cluster = int.from_bytes(boot[48:56], "little")

print(f"OEM: {oem}")                    # NTFS
print(f"Bytes/sector: {bps}")            # 512
print(f"Sectors/cluster: {spc}")         # 8
print(f"MFT at cluster: {mft_cluster}")  # e.g. 786432
```

## 3. Check if a File is Resident

```python
from ntfs_toolkit.analyzers import ResidencyChecker

checker = ResidencyChecker()

# Small files are usually resident
print(checker.is_file_resident(r"C:\Windows\win.ini"))  # likely True

# Large files are non-resident
print(checker.is_file_resident(r"C:\Windows\explorer.exe"))  # False
```

## 4. Parse an MFT Record

```python
from ntfs_toolkit.analyzers import MFTParser, FileAnalyzer

fa = FileAnalyzer()
vol = fa.get_volume_info("C")

parser = MFTParser()

# Read MFT record #0 ($MFT itself)
raw = parser.read_mft_record(
    "C", vol["mft_start_lcn"], vol["bytes_per_cluster"],
    vol["mft_record_size"], record_index=0
)

header = parser.parse_mft_header(raw)
print(f"Signature: {header['signature']}")       # b'FILE'
print(f"Flags: {header['flags_description']}")   # IN_USE
print(f"Used: {header['bytes_in_use']} bytes")

attrs = parser.parse_mft_attributes(raw)
for attr in attrs:
    print(f"$DATA: resident={attr['is_resident']}, "
          f"stream='{attr['stream_name'] or 'unnamed'}'")
```

## 5. Verify LBA Calculation

```python
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer

ca = ComprehensiveAnalyzer()
result = ca.analyze(r"C:\Windows\notepad.exe")

if not result["is_resident"] and result["extents"]:
    ext = result["extents"][0]
    check = ca.verify_content(r"C:\Windows\notepad.exe", ext)

    print(f"Physical drive bytes match file: {check['physical_match']}")
    print(f"Volume bytes match file:         {check['volume_match']}")
    print(f"First 32 bytes (hex): {check['file_api'].hex()}")
```

## 6. Scan Multiple Files

```python
import os
from ntfs_toolkit.analyzers import FileAnalyzer, ResidencyChecker

fa = FileAnalyzer()
rc = ResidencyChecker()

for entry in os.scandir(r"C:\Windows"):
    if entry.is_file():
        try:
            info = fa.get_file_info(entry.path)
            res = rc.is_file_resident(entry.path)
            print(f"{entry.name:30s}  MFT#{info['mft_record_number']:>8,}  "
                  f"{'RESIDENT' if res else 'NON-RES':>10s}  "
                  f"{entry.stat().st_size:>12,} bytes")
        except Exception:
            pass
```

## 7. Share a Single DiskIO Instance

```python
from ntfs_toolkit.core import DiskIO
from ntfs_toolkit.analyzers import (
    LBAReader, FileAnalyzer, ExtentMapper, MFTParser,
)

# One DiskIO instance — one privilege escalation
dio = DiskIO()

reader   = LBAReader(dio)
analyzer = FileAnalyzer(dio)
mapper   = ExtentMapper(dio)
parser   = MFTParser(dio)

# All share the same connection
vol = analyzer.get_volume_info("C")
data = reader.read_volume("C", 0, 512)
```

## 8. Write to a Specific LBA (Dangerous)

```python
from ntfs_toolkit.dangerous import LBAWriter

writer = LBAWriter()

# This will show current content and ask for YES confirmation
writer.write_volume("D", lba=2048, data=b"Hello from NTFS Toolkit!")

# Skip confirmation (use with extreme caution)
writer.write_volume("D", lba=2048, data=b"No confirm", confirm=False)
```
