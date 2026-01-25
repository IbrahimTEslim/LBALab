import ctypes
import os
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3

# Partition styles
PARTITION_STYLE_MBR = 0
PARTITION_STYLE_GPT = 1
PARTITION_STYLE_RAW = 2

# Structures
class STARTING_VCN_INPUT_BUFFER(ctypes.Structure):
    _fields_ = [("StartingVcn", ctypes.c_longlong)]

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

# Open file handle
def open_file(path):
    path = r"\\?\\{}".format(os.path.abspath(path))
    handle = ctypes.windll.kernel32.CreateFileW(
        path,
        GENERIC_READ,
        0,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if handle == -1:
        raise ctypes.WinError()
    return handle

# Proper structure for RETRIEVAL_POINTERS_BUFFER
class RETRIEVAL_POINTERS_BUFFER(ctypes.Structure):
    _fields_ = [
        ("ExtentCount", ctypes.c_uint32),
        ("StartingVcn", ctypes.c_ulonglong),
        # Followed by ExtentCount pairs of (NextVcn, Lcn)
    ]

class EXTENT_PAIR(ctypes.Structure):
    _fields_ = [
        ("NextVcn", ctypes.c_ulonglong),
        ("Lcn", ctypes.c_ulonglong),
    ]

# Get extents of file (VCN → LCN)
def get_file_extents(file_handle):
    input_buffer = STARTING_VCN_INPUT_BUFFER(0)
    out_size = 4096
    output_buffer = ctypes.create_string_buffer(out_size)
    returned = wintypes.DWORD()

    res = ctypes.windll.kernel32.DeviceIoControl(
        file_handle,
        FSCTL_GET_RETRIEVAL_POINTERS,
        ctypes.byref(input_buffer),
        ctypes.sizeof(input_buffer),
        output_buffer,
        out_size,
        ctypes.byref(returned),
        None
    )

    # If error indicates file is resident, return None
    if not res:
        err = ctypes.GetLastError()
        if err == 1:  # ERROR_INVALID_FUNCTION
            return None
        raise ctypes.WinError(err)

    # Debug: print first 64 bytes of buffer in hex
    print("Raw buffer (first 64 bytes):")
    for i in range(min(64, returned.value)):
        if i % 16 == 0:
            print(f"\n{i:04x}: ", end="")
        print(f"{ord(output_buffer[i]):02x} ", end="")
    print("\n")

    # Parse manually with proper error checking
    if returned.value < 12:
        raise ValueError("Buffer too small for RETRIEVAL_POINTERS_BUFFER header")
    
    extent_count = int.from_bytes(output_buffer[0:4], 'little')
    starting_vcn = int.from_bytes(output_buffer[8:16], 'little')  # Skip 4 bytes padding after ExtentCount
    
    print(f"Debug: ExtentCount = {extent_count}, StartingVcn = {starting_vcn}")
    print(f"Debug: Bytes returned = {returned.value}")
    
    if extent_count > 10000:  # More reasonable sanity check for large/fragmented files
        raise ValueError(f"ExtentCount {extent_count} seems too large")
    
    expected_size = 16 + extent_count * 16  # 16 byte header + 16 bytes per extent
    if returned.value < expected_size:
        raise ValueError(f"Buffer size {returned.value} too small for {extent_count} extents")
    
    extents = []
    current_vcn = starting_vcn
    
    for i in range(extent_count):
        # Each extent pair is 16 bytes starting at offset 16
        offset = 16 + i * 16
        
        next_vcn = int.from_bytes(output_buffer[offset:offset+8], 'little')
        lcn_raw = output_buffer[offset+8:offset+16]
        
        # Check for sparse extent (all FF bytes)
        if lcn_raw == b'\xff' * 8:
            lcn = -1
        else:
            lcn = int.from_bytes(lcn_raw, 'little')
            
        print(f"Debug: Extent {i}: offset={offset}, raw_next_vcn={output_buffer[offset:offset+8].hex()}, raw_lcn={lcn_raw.hex()}")
        print(f"Debug: Extent {i}: VCN {current_vcn}-{next_vcn-1}, LCN {lcn}")
        
        extents.append((current_vcn, next_vcn, lcn))
        current_vcn = next_vcn

    return extents

# Get partition start LBA
def get_partition_start_lba(drive_letter):
    volume_path = r"\\.\{}:".format(drive_letter)
    handle = ctypes.windll.kernel32.CreateFileW(
        volume_path,
        0,
        1,  # FILE_SHARE_READ
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if handle == -1:
        raise ctypes.WinError()

    part_info = PARTITION_INFORMATION_EX()
    returned = wintypes.DWORD()
    
    try:
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
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

    bytes_per_sector = 512
    starting_lba = part_info.StartingOffset // bytes_per_sector
    return starting_lba

# Get sectors per cluster
def get_sectors_per_cluster(drive_letter):
    sectors_per_cluster = wintypes.DWORD()
    bytes_per_sector = wintypes.DWORD()
    free_clusters = wintypes.DWORD()
    total_clusters = wintypes.DWORD()

    res = ctypes.windll.kernel32.GetDiskFreeSpaceW(
        ctypes.c_wchar_p(drive_letter + ":\\"),
        ctypes.byref(sectors_per_cluster),
        ctypes.byref(bytes_per_sector),
        ctypes.byref(free_clusters),
        ctypes.byref(total_clusters)
    )
    if not res:
        raise ctypes.WinError()

    return sectors_per_cluster.value, bytes_per_sector.value

# Main
if __name__ == "__main__":
    file_path = input("Enter NTFS file path: ")
    drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")

    try:
        partition_starting_LBA = get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = get_sectors_per_cluster(drive_letter)

        handle = open_file(file_path)
        extents = get_file_extents(handle)
        ctypes.windll.kernel32.CloseHandle(handle)

        print(f"\nPartition starting LBA: {partition_starting_LBA}")
        print(f"Sectors per cluster: {sectors_per_cluster}")
        print(f"Bytes per sector: {bytes_per_sector}")

        if extents is None:
            print("\nFile is resident (data stored inside MFT record)")
        else:
            print("\nVCN → LCN → LBA mapping:")
            for start_vcn, next_vcn, lcn in extents:
                cluster_count = next_vcn - start_vcn
                if lcn == -1:
                    print(f"VCN {start_vcn}-{next_vcn-1} ({cluster_count} clusters) : Sparse (not allocated)")
                else:
                    lba = partition_starting_LBA + (lcn * sectors_per_cluster)
                    cluster_size = sectors_per_cluster * bytes_per_sector
                    byte_offset = lba * bytes_per_sector
                    size_bytes = cluster_count * cluster_size
                    print(f"VCN {start_vcn}-{next_vcn-1} ({cluster_count} clusters, {size_bytes} bytes) : LCN {lcn} : LBA {lba} : Byte offset {byte_offset}")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to run as administrator for low-level disk access.")