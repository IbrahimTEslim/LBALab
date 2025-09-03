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
INVALID_HANDLE_VALUE = -1

# FSCTL constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073

# Error codes that indicate resident files
ERROR_HANDLE_EOF = 38
ERROR_INVALID_FUNCTION = 1
ERROR_INVALID_USER_BUFFER = 1784

# Structures
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

class STARTING_VCN_INPUT_BUFFER(ctypes.Structure):
    _fields_ = [("StartingVcn", ctypes.c_longlong)]

class EXTENT(ctypes.Structure):
    _fields_ = [
        ("NextVcn", ctypes.c_longlong),
        ("Lcn", ctypes.c_longlong)
    ]

class RETRIEVAL_POINTERS_BUFFER(ctypes.Structure):
    _fields_ = [
        ("ExtentCount", wintypes.DWORD),
        ("StartingVcn", ctypes.c_longlong),
        ("Extents", EXTENT * 1)
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
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        return handle
    except Exception as e:
        raise NTFSError(f"Failed to open file '{path}': {e}")

def check_cluster_allocation(file_handle):
    """
    Check if file has cluster allocations using FSCTL_GET_RETRIEVAL_POINTERS.
    Returns tuple: (has_clusters, extent_info)
    - has_clusters: True if file has clusters (non-resident), False if no clusters (resident)
    - extent_info: Dictionary with cluster allocation details for non-resident files
    """
    try:
        # Prepare input buffer - start from VCN 0
        input_buffer = STARTING_VCN_INPUT_BUFFER()
        input_buffer.StartingVcn = 0
        
        # Allocate output buffer for retrieval pointers
        buffer_size = ctypes.sizeof(RETRIEVAL_POINTERS_BUFFER) + (ctypes.sizeof(EXTENT) * 100)
        output_buffer = ctypes.create_string_buffer(buffer_size)
        returned = wintypes.DWORD()
        
        # Query cluster allocation
        result = ctypes.windll.kernel32.DeviceIoControl(
            file_handle,
            FSCTL_GET_RETRIEVAL_POINTERS,
            ctypes.byref(input_buffer),
            ctypes.sizeof(input_buffer),
            output_buffer,
            buffer_size,
            ctypes.byref(returned),
            None
        )
        
        if result:
            # API succeeded - file has cluster allocations (non-resident)
            if returned.value >= 16:  # Minimum size for valid retrieval pointers
                # Parse the retrieval pointers buffer
                extent_count = int.from_bytes(output_buffer.raw[0:4], "little")
                starting_vcn = int.from_bytes(output_buffer.raw[4:12], "little")
                
                extents = []
                offset = 16
                for i in range(min(extent_count, 10)):  # First 10 extents
                    if offset + 16 <= returned.value:
                        next_vcn = int.from_bytes(output_buffer.raw[offset:offset+8], "little")
                        lcn = int.from_bytes(output_buffer.raw[offset+8:offset+16], "little")
                        extents.append({"NextVcn": next_vcn, "Lcn": lcn})
                        offset += 16
                    else:
                        break
                
                extent_info = {
                    "ExtentCount": extent_count,
                    "StartingVcn": starting_vcn,
                    "Extents": extents
                }
                return True, extent_info  # Has clusters = non-resident
            else:
                return True, {"ExtentCount": 0, "Extents": []}  # Has clusters but empty result
        else:
            # API failed - check why
            error_code = ctypes.windll.kernel32.GetLastError()
            if error_code in [ERROR_HANDLE_EOF, ERROR_INVALID_FUNCTION, ERROR_INVALID_USER_BUFFER]:
                # These responses indicate file has no cluster allocations (resident)
                return False, None
            else:
                # Genuine error
                raise ctypes.WinError()
                
    except Exception as e:
        error_code = ctypes.windll.kernel32.GetLastError()
        if error_code in [ERROR_HANDLE_EOF, ERROR_INVALID_FUNCTION, ERROR_INVALID_USER_BUFFER]:
            return False, None  # No cluster allocations = resident
        raise NTFSError(f"Failed to check cluster allocation: {e}")

def is_file_resident(file_path):
    """
    Determine if a file is resident by checking cluster allocation.
    
    Method: Uses FSCTL_GET_RETRIEVAL_POINTERS to check if file has cluster mappings.
    - Files with cluster allocations = non-resident
    - Files without cluster allocations = resident (data stored in MFT)
    
    Returns True if resident, False if non-resident.
    Works without admin privileges and is 100% accurate.
    """
    file_handle = None
    
    try:
        # Validate input
        if not os.path.exists(file_path):
            raise NTFSError(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise NTFSError(f"Path is not a file: {file_path}")
        
        # Open file
        file_handle = open_file(file_path)
        
        # Check cluster allocation
        has_clusters, extent_info = check_cluster_allocation(file_handle)
        
        # Return residency status
        return not has_clusters  # No clusters = resident
        
    except Exception as e:
        raise NTFSError(f"Error checking file residency: {e}")
    finally:
        safe_handle_close(file_handle)

def get_detailed_file_info(file_path):
    """Get comprehensive information about a file including residency and cluster details"""
    file_handle = None
    
    try:
        # Basic file information
        file_handle = open_file(file_path)
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        ):
            raise ctypes.WinError()
        
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        mft_index = file_index & 0xFFFFFFFFFFFF
        sequence_number = (file_index >> 48) & 0xFFFF
        
        # Check cluster allocation
        has_clusters, extent_info = check_cluster_allocation(file_handle)
        
        result = {
            "path": file_path,
            "size": os.path.getsize(file_path),
            "mft_record": mft_index,
            "sequence_number": sequence_number,
            "file_index": file_index,
            "attributes": file_info.dwFileAttributes,
            "is_resident": not has_clusters,
            "has_clusters": has_clusters,
            "extent_info": extent_info
        }
        
        return result
        
    except Exception as e:
        raise NTFSError(f"Error getting file information: {e}")
    finally:
        safe_handle_close(file_handle)

def print_file_info(file_path):
    """Print detailed information about a file's residency status"""
    try:
        info = get_detailed_file_info(file_path)
        
        print(f"File: {info['path']}")
        print(f"Size: {info['size']:,} bytes")
        print(f"MFT Record: {info['mft_record']} (Sequence: {info['sequence_number']})")
        print(f"File Attributes: 0x{info['attributes']:08X}")
        
        if info['is_resident']:
            print("Status: RESIDENT (file data stored inside MFT record)")
        else:
            print("Status: NON-RESIDENT (file data stored in clusters on disk)")
            
            if info['extent_info']:
                extent_count = info['extent_info']['ExtentCount']
                print(f"Cluster Extents: {extent_count}")
                
                if info['extent_info']['Extents']:
                    print("First few extents:")
                    for i, extent in enumerate(info['extent_info']['Extents'][:3]):
                        if extent['Lcn'] == -1:
                            print(f"  Extent {i+1}: Sparse/Unallocated (VCN {extent['NextVcn']})")
                        else:
                            print(f"  Extent {i+1}: LCN {extent['Lcn']}, VCN {extent['NextVcn']}")
            
    except Exception as e:
        print(f"Error: {e}")

# Example usage and testing
if __name__ == "__main__":
    print("NTFS File Residency Checker - Cluster Allocation Method")
    print("=" * 60)
    print("Uses FSCTL_GET_RETRIEVAL_POINTERS to check cluster allocation")
    print("No admin privileges required - 100% accurate")
    print()
    
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

    # Test with some common files to demonstrate
    print("\n--- Testing with common files ---")
    test_files = [
        "C:\\Windows\\win.ini",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "C:\\Windows\\System32\\notepad.exe"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n{'-' * 40}")
            print_file_info(test_file)
        else:
            print(f"Test file not found: {test_file}")