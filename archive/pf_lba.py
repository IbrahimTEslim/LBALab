import ctypes
import sys
from ctypes import wintypes

# Windows constants
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
OPEN_EXISTING = 3

# Partition styles
PARTITION_STYLE_MBR = 0
PARTITION_STYLE_GPT = 1
PARTITION_STYLE_RAW = 2

# Structures
class MBR_PARTITION_INFO(ctypes.Structure):
    _fields_ = [
        ("PartitionType", ctypes.c_byte),
        ("BootIndicator", ctypes.c_byte),
        ("RecognizedPartition", ctypes.c_byte),
        ("HiddenSectors", ctypes.c_uint32)
    ]

class GPT_PARTITION_INFO(ctypes.Structure):
    _fields_ = [
        ("PartitionType", ctypes.c_byte * 16),  # GUID
        ("PartitionId", ctypes.c_byte * 16),    # GUID
        ("Attributes", ctypes.c_longlong),
        ("Name", ctypes.c_wchar * 36)
    ]

class PARTITION_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("Mbr", MBR_PARTITION_INFO),
        ("Gpt", GPT_PARTITION_INFO)
    ]

class PARTITION_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", ctypes.c_int),
        ("StartingOffset", ctypes.c_longlong),
        ("PartitionLength", ctypes.c_longlong),
        ("PartitionNumber", ctypes.c_uint32),
        ("RewritePartition", ctypes.c_byte),
        ("IsServicePartition", ctypes.c_byte),
        ("Padding", ctypes.c_byte * 2),  # Alignment padding
        ("PartitionInfo", PARTITION_INFO_UNION)
    ]

def get_partition_info(drive_letter):
    """
    Get partition information for a given drive letter.
    Returns tuple: (starting_lba, partition_length_sectors, partition_style, partition_number)
    """
    # Normalize drive letter
    drive_letter = drive_letter.upper().replace(':', '')
    if len(drive_letter) != 1 or not drive_letter.isalpha():
        raise ValueError("Drive letter must be a single letter (A-Z)")
    
    volume_path = rf"\\.\{drive_letter}:"
    
    # Open volume handle
    handle = ctypes.windll.kernel32.CreateFileW(
        volume_path,
        0,  # No access needed, just query
        1,  # FILE_SHARE_READ
        None,
        OPEN_EXISTING,
        0,
        None
    )
    
    if handle == -1:
        error = ctypes.GetLastError()
        if error == 2:  # ERROR_FILE_NOT_FOUND
            raise FileNotFoundError(f"Drive {drive_letter}: not found")
        elif error == 5:  # ERROR_ACCESS_DENIED
            raise PermissionError("Access denied. Run as administrator.")
        else:
            raise ctypes.WinError(error)

    try:
        # Get partition information
        part_info = PARTITION_INFORMATION_EX()
        returned = wintypes.DWORD()
        
        res = ctypes.windll.kernel32.DeviceIoControl(
            handle,
            IOCTL_DISK_GET_PARTITION_INFO_EX,
            None,
            0,
            ctypes.byref(part_info),
            ctypes.sizeof(part_info),
            ctypes.byref(returned),
            None
        )
        
        if not res:
            raise ctypes.WinError()
        
        # Calculate LBA (assuming 512 bytes per sector)
        bytes_per_sector = 512
        starting_lba = part_info.StartingOffset // bytes_per_sector
        partition_length_sectors = part_info.PartitionLength // bytes_per_sector
        
        # Get partition style name
        style_names = {
            PARTITION_STYLE_MBR: "MBR",
            PARTITION_STYLE_GPT: "GPT", 
            PARTITION_STYLE_RAW: "RAW"
        }
        style_name = style_names.get(part_info.PartitionStyle, "Unknown")
        
        return (starting_lba, partition_length_sectors, style_name, part_info.PartitionNumber)
        
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

def main():
    if len(sys.argv) != 2:
        print("Usage: python partition_lba.py <drive_letter>")
        print("Example: python partition_lba.py C")
        print("         python partition_lba.py D:")
        sys.exit(1)
    
    drive_letter = sys.argv[1]
    
    try:
        starting_lba, length_sectors, style, partition_num = get_partition_info(drive_letter)
        
        print(f"Drive {drive_letter.upper()}:")
        print(f"  Starting LBA: {starting_lba:,}")
        print(f"  Length (sectors): {length_sectors:,}")
        print(f"  Length (bytes): {length_sectors * 512:,}")
        print(f"  Length (MB): {(length_sectors * 512) // (1024 * 1024):,}")
        print(f"  Length (GB): {(length_sectors * 512) // (1024 * 1024 * 1024):,}")
        print(f"  Partition style: {style}")
        print(f"  Partition number: {partition_num}")
        
        # Calculate ending LBA
        ending_lba = starting_lba + length_sectors - 1
        print(f"  Ending LBA: {ending_lba:,}")
        
    except Exception as e:
        print(f"Error: {e}")
        if "Access denied" in str(e):
            print("Make sure to run as administrator.")
        sys.exit(1)

if __name__ == "__main__":
    main()