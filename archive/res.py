import ctypes
from ctypes import wintypes
import os
import sys

# Constants
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
INVALID_HANDLE_VALUE = -1

# Attribute types
ATTR_STANDARD_INFORMATION = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME = 0x30
ATTR_OBJECT_ID = 0x40
ATTR_SECURITY_DESCRIPTOR = 0x50
ATTR_VOLUME_NAME = 0x60
ATTR_VOLUME_INFORMATION = 0x70
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_INDEX_ALLOCATION = 0xA0
ATTR_BITMAP = 0xB0
ATTR_REPARSE_POINT = 0xC0
ATTR_EA_INFORMATION = 0xD0
ATTR_EA = 0xE0
ATTR_PROPERTY_SET = 0xF0
ATTR_LOGGED_UTILITY_STREAM = 0x100
ATTR_END = 0xFFFFFFFF

# Structures
class FILE_INTERNAL_INFORMATION(ctypes.Structure):
    _fields_ = [("IndexNumber", ctypes.c_longlong)]

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

class NTFSError(Exception):
    """Custom exception for NTFS-related errors"""
    pass

def safe_handle_close(handle):
    """Safely close a handle if it's valid"""
    if handle and handle != INVALID_HANDLE_VALUE:
        ctypes.windll.kernel32.CloseHandle(handle)

def open_file(path):
    """Open a file handle with proper error handling"""
    try:
        path = r"\\?\{}".format(os.path.abspath(path))
        handle = ctypes.windll.kernel32.CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | 2 | 4,  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            None,
            OPEN_EXISTING,
            0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS - allows opening files that might be in use
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        return handle
    except Exception as e:
        raise NTFSError(f"Failed to open file '{path}': {e}")

def open_volume(drive_letter):
    """Open a volume handle with proper error handling"""
    try:
        volume_path = r"\\.\{}:".format(drive_letter)
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        return handle
    except Exception as e:
        raise NTFSError(f"Failed to open volume '{drive_letter}:': {e}")

def get_ntfs_volume_data(vol_handle):
    """Get NTFS volume information"""
    try:
        vol_info = NTFS_VOLUME_DATA_BUFFER()
        returned = wintypes.DWORD()
        res = ctypes.windll.kernel32.DeviceIoControl(
            vol_handle,
            FSCTL_GET_NTFS_VOLUME_DATA,
            None,
            0,
            ctypes.byref(vol_info),
            ctypes.sizeof(vol_info),
            ctypes.byref(returned),
            None
        )
        if not res:
            raise ctypes.WinError()
        return vol_info
    except Exception as e:
        raise NTFSError(f"Failed to get NTFS volume data: {e}")

def read_mft_record(drive_letter, mft_start_lcn, bytes_per_cluster, mft_record_size, mft_index):
    """Read an MFT record from the volume"""
    handle = None
    try:
        handle = open_volume(drive_letter)
        
        # Calculate offset in bytes
        offset = (mft_start_lcn * bytes_per_cluster) + (mft_index * mft_record_size)
        
        # Set file pointer using 64-bit offset
        high = ctypes.c_long(offset >> 32)
        low = ctypes.c_long(offset & 0xFFFFFFFF)
        
        result = ctypes.windll.kernel32.SetFilePointer(handle, low, ctypes.byref(high), 0)
        if result == INVALID_HANDLE_VALUE and ctypes.windll.kernel32.GetLastError() != 0:
            raise ctypes.WinError()
        
        # Read MFT record
        buf = ctypes.create_string_buffer(mft_record_size)
        read = wintypes.DWORD()
        
        if not ctypes.windll.kernel32.ReadFile(handle, buf, mft_record_size, ctypes.byref(read), None):
            raise ctypes.WinError()
            
        if read.value != mft_record_size:
            raise NTFSError(f"Only read {read.value} bytes, expected {mft_record_size}")
            
        return buf.raw
        
    except Exception as e:
        raise NTFSError(f"Failed to read MFT record {mft_index}: {e}")
    finally:
        safe_handle_close(handle)

def parse_mft_attributes(mft_data):
    """Parse MFT record to find $DATA attribute and check residency"""
    try:
        # Verify MFT signature
        if len(mft_data) < 4 or mft_data[:4] != b'FILE':
            raise NTFSError("Invalid MFT record signature")
        
        # Get first attribute offset (usually 0x30 for newer NTFS, 0x20 for older)
        if len(mft_data) < 0x16:
            raise NTFSError("MFT record too small")
            
        first_attr_offset = int.from_bytes(mft_data[0x14:0x16], "little")
        
        if first_attr_offset >= len(mft_data):
            raise NTFSError("Invalid first attribute offset")
        
        # Scan attributes
        offset = first_attr_offset
        data_attributes = []
        
        while offset < len(mft_data) - 8:  # Need at least 8 bytes for header
            # Read attribute type
            attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
            
            # End of attributes
            if attr_type == ATTR_END or attr_type == 0:
                break
            
            # Read attribute length
            if offset + 8 > len(mft_data):
                break
            attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
            
            # Validate attribute length
            if attr_length == 0 or attr_length > len(mft_data) - offset:
                break
            
            # Check if this is a $DATA attribute
            if attr_type == ATTR_DATA:
                # Read non-resident flag (at offset 8 from attribute start)
                if offset + 9 <= len(mft_data):
                    non_resident_flag = mft_data[offset + 8]
                    data_attributes.append({
                        'offset': offset,
                        'is_resident': non_resident_flag == 0,
                        'length': attr_length
                    })
            
            # Move to next attribute
            offset += attr_length
        
        return data_attributes
        
    except Exception as e:
        raise NTFSError(f"Failed to parse MFT attributes: {e}")

def is_file_resident(file_path):
    """
    Check if a file is resident (stored within MFT record) or non-resident.
    Returns True if resident, False if non-resident.
    """
    file_handle = None
    vol_handle = None
    
    try:
        # Validate input
        if not os.path.exists(file_path):
            raise NTFSError(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise NTFSError(f"Path is not a file: {file_path}")
        
        # Get drive letter
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        if not drive_letter:
            raise NTFSError("Could not determine drive letter")
        
        # Open file to get MFT record number
        file_handle = open_file(file_path)
        
        # Get file's information using GetFileInformationByHandle
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        ):
            raise ctypes.WinError()
        
        # Combine high and low parts to get the full file index (MFT record number)
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        
        # The file index contains the MFT record number in the lower 48 bits
        # The upper 16 bits contain the sequence number - we need to mask it out
        mft_index = file_index & 0xFFFFFFFFFFFF  # Keep only lower 48 bits
        safe_handle_close(file_handle)
        file_handle = None
        
        # Get volume information
        vol_handle = open_volume(drive_letter)
        vol_info = get_ntfs_volume_data(vol_handle)
        safe_handle_close(vol_handle)
        vol_handle = None
        
        # Read MFT record
        mft_data = read_mft_record(
            drive_letter, 
            vol_info.MftStartLcn, 
            vol_info.BytesPerCluster,  # Fixed: was using BytesPerSector incorrectly
            vol_info.BytesPerFileRecordSegment, 
            mft_index
        )
        
        # Parse attributes to find $DATA
        data_attributes = parse_mft_attributes(mft_data)
        
        if not data_attributes:
            # No $DATA attribute found - might be a directory or special file
            return None
        
        # Check the first (unnamed) $DATA attribute
        # Files can have multiple $DATA attributes (named streams)
        first_data_attr = data_attributes[0]
        return first_data_attr['is_resident']
        
    except Exception as e:
        raise NTFSError(f"Error checking file residency: {e}")
    finally:
        safe_handle_close(file_handle)
        safe_handle_close(vol_handle)

def print_file_info(file_path):
    """Print detailed information about a file's residency status"""
    try:
        # Get basic file info first
        file_handle = open_file(file_path)
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        ):
            safe_handle_close(file_handle)
            raise ctypes.WinError()
        
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        mft_index = file_index & 0xFFFFFFFFFFFF
        safe_handle_close(file_handle)
        
        file_size = os.path.getsize(file_path)
        
        print(f"File: {file_path}")
        print(f"Size: {file_size:,} bytes")
        print(f"File Index: {file_index} (0x{file_index:016X})")
        print(f"MFT Record: {mft_index} (0x{mft_index:012X})")
        
        result = is_file_resident(file_path)
        
        if result is None:
            print("Status: No $DATA attribute found (likely a directory or special file)")
        elif result:
            print("Status: RESIDENT (file data stored inside MFT record)")
        else:
            print("Status: NON-RESIDENT (file data stored in clusters on disk)")
            
    except Exception as e:
        print(f"Error: {e}")

# Example usage and testing
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Use command line argument if provided
        file_path = sys.argv[1]
        print_file_info(file_path)
    else:
        # Interactive mode
        while True:
            try:
                path = input("\nEnter NTFS file path (or 'quit' to exit): ").strip()
                if path.lower() in ['quit', 'exit', 'q']:
                    break
                if path:
                    print_file_info(path)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break

    # Test with some common small files that are likely to be resident
    print("\n--- Testing with common system files ---")
    test_files = [
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "C:\\Windows\\System32\\notepad.exe",
        "C:\\Windows\\win.ini"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print_file_info(test_file)
        else:
            print(f"Test file not found: {test_file}")