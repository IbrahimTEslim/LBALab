import ctypes
import os
import sys
from ctypes import wintypes

# Windows constants
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = -1

class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]

class NTFS_VOLUME_DATA_BUFFER(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_longlong),
        ("NumberSectors", ctypes.c_longlong),
        ("TotalClusters", ctypes.c_longlong),
        ("FreeClusters", ctypes.c_longlong),
        ("TotalReserved", ctypes.c_longlong),
        ("BytesPerSector", ctypes.c_uint32),
        ("BytesPerCluster", ctypes.c_uint32),
        ("BytesPerFileRecordSegment", ctypes.c_uint32),
        ("ClustersPerFileRecordSegment", ctypes.c_uint32),
        ("MftValidDataLength", ctypes.c_longlong),
        ("MftStartLcn", ctypes.c_longlong),
        ("Mft2StartLcn", ctypes.c_longlong),
        ("MftZoneStart", ctypes.c_longlong),
        ("MftZoneEnd", ctypes.c_longlong)
    ]

class PARTITION_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", ctypes.c_int),
        ("StartingOffset", ctypes.c_longlong),
        ("PartitionLength", ctypes.c_longlong),
        ("PartitionNumber", ctypes.c_uint32),
        ("RewritePartition", ctypes.c_byte),
        ("IsServicePartition", ctypes.c_byte),
        ("Padding", ctypes.c_byte * 2),
        ("PartitionInfo", ctypes.c_byte * 112)  # Union placeholder
    ]

def open_volume(drive_letter):
    volume_path = f"\\\\.\\{drive_letter}:"
    handle = ctypes.windll.kernel32.CreateFileW(
        volume_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING, 0, None
    )
    if handle == INVALID_HANDLE_VALUE:
        raise Exception(f"Cannot open volume {drive_letter}:")
    return handle

def get_ntfs_volume_data(vol_handle):
    vol_info = NTFS_VOLUME_DATA_BUFFER()
    returned = wintypes.DWORD()
    res = ctypes.windll.kernel32.DeviceIoControl(
        vol_handle, FSCTL_GET_NTFS_VOLUME_DATA, None, 0,
        ctypes.byref(vol_info), ctypes.sizeof(vol_info), ctypes.byref(returned), None
    )
    if not res:
        raise Exception("Cannot get NTFS volume data")
    return vol_info

def get_partition_start_lba(drive_letter):
    handle = open_volume(drive_letter)
    try:
        part_info = PARTITION_INFORMATION_EX()
        returned = wintypes.DWORD()
        res = ctypes.windll.kernel32.DeviceIoControl(
            handle, IOCTL_DISK_GET_PARTITION_INFO_EX, None, 0,
            ctypes.byref(part_info), ctypes.sizeof(part_info), ctypes.byref(returned), None
        )
        if not res:
            raise Exception("Cannot get partition info")
        return part_info.StartingOffset // 512
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

def get_file_mft_record_number(file_path):
    abs_path = f"\\\\?\\{os.path.abspath(file_path)}"
    handle = ctypes.windll.kernel32.CreateFileW(
        abs_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
    )
    if handle == INVALID_HANDLE_VALUE:
        raise Exception(f"Cannot open file {file_path}")
    
    try:
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(handle, ctypes.byref(file_info)):
            raise Exception("Cannot get file information")
        
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        mft_record_number = file_index & 0xFFFFFFFFFFFF
        return mft_record_number
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

def read_mft_record_raw(drive_letter, mft_record_number):
    """Fixed MFT record reading with proper sector alignment"""
    vol_handle = open_volume(drive_letter)
    try:
        vol_info = get_ntfs_volume_data(vol_handle)
        
        # Calculate MFT record offset in bytes
        mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
        record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
        absolute_offset = mft_start_bytes + record_offset_bytes
        
        # Seek to position
        high = ctypes.c_long(absolute_offset >> 32)
        low = ctypes.c_long(absolute_offset & 0xFFFFFFFF)
        result = ctypes.windll.kernel32.SetFilePointer(vol_handle, low, ctypes.byref(high), 0)
        
        if result == INVALID_HANDLE_VALUE and ctypes.windll.kernel32.GetLastError() != 0:
            raise Exception(f"Cannot seek to MFT record {mft_record_number}")
        
        # Read MFT record
        buffer = ctypes.create_string_buffer(vol_info.BytesPerFileRecordSegment)
        bytes_read = wintypes.DWORD()
        
        if not ctypes.windll.kernel32.ReadFile(vol_handle, buffer, vol_info.BytesPerFileRecordSegment, ctypes.byref(bytes_read), None):
            raise Exception(f"Cannot read MFT record {mft_record_number}")
        
        if bytes_read.value != vol_info.BytesPerFileRecordSegment:
            raise Exception(f"Read {bytes_read.value} bytes, expected {vol_info.BytesPerFileRecordSegment}")
        
        return buffer.raw
    finally:
        ctypes.windll.kernel32.CloseHandle(vol_handle)

def analyze_mft_record(mft_data):
    """Analyze MFT record structure"""
    if len(mft_data) < 48:
        return {"valid": False, "error": "Record too small"}
    
    signature = mft_data[0:4]
    if signature != b'FILE':
        return {"valid": False, "error": f"Invalid signature: {signature}"}
    
    flags = int.from_bytes(mft_data[22:24], 'little')
    attrs_offset = int.from_bytes(mft_data[20:22], 'little')
    
    return {
        "valid": True,
        "signature": signature,
        "in_use": bool(flags & 0x0001),
        "is_directory": bool(flags & 0x0002),
        "attrs_offset": attrs_offset
    }

def main():
    print("Fixed MFT Record Analyzer")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Get MFT record number from file path")
        print("2. Fetch MFT record by number")
        print("3. Quit")
        
        choice = input("\nChoose (1-3): ").strip()
        
        if choice == "1":
            file_path = input("Enter file path: ").strip().strip('"')
            if not os.path.exists(file_path):
                print("File does not exist!")
                continue
            
            try:
                drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
                mft_record_number = get_file_mft_record_number(file_path)
                
                print(f"\nFile: {file_path}")
                print(f"Drive: {drive_letter}:")
                print(f"MFT Record Number: {mft_record_number}")
                
                # Calculate LBA
                vol_handle = open_volume(drive_letter)
                vol_info = get_ntfs_volume_data(vol_handle)
                ctypes.windll.kernel32.CloseHandle(vol_handle)
                
                partition_start_lba = get_partition_start_lba(drive_letter)
                
                # Fixed calculation
                mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
                record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
                absolute_offset = mft_start_bytes + record_offset_bytes
                
                # Convert to LBA (512 bytes per sector)
                relative_lba = absolute_offset // 512
                absolute_lba = partition_start_lba + relative_lba
                
                print(f"MFT Record LBA (relative): {relative_lba}")
                print(f"MFT Record LBA (absolute): {absolute_lba}")
                
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "2":
            try:
                mft_record_number = int(input("Enter MFT record number: ").strip())
                drive_letter = input("Enter drive letter (default D): ").strip().upper() or "D"
                
                print(f"\nFetching MFT record {mft_record_number} from drive {drive_letter}:")
                
                mft_data = read_mft_record_raw(drive_letter, mft_record_number)
                analysis = analyze_mft_record(mft_data)
                
                print(f"Record size: {len(mft_data)} bytes")
                print(f"Valid: {analysis['valid']}")
                
                if analysis['valid']:
                    print(f"In use: {analysis['in_use']}")
                    print(f"Is directory: {analysis['is_directory']}")
                    
                    # Show first 64 bytes as hex
                    print("\nFirst 64 bytes (hex):")
                    for i in range(0, min(64, len(mft_data)), 16):
                        hex_line = ' '.join(f'{b:02X}' for b in mft_data[i:i+16])
                        ascii_line = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in mft_data[i:i+16])
                        print(f"{i:04X}: {hex_line:<48} | {ascii_line}")
                else:
                    print(f"Error: {analysis['error']}")
                    # Show raw data for debugging
                    print("\nFirst 32 bytes (hex):")
                    hex_data = ' '.join(f'{b:02X}' for b in mft_data[:32])
                    print(hex_data)
                
            except ValueError:
                print("Invalid MFT record number!")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "3":
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main()