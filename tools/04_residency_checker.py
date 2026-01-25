#!/usr/bin/env python3
"""
File Residency Checker - NTFS Resident vs Non-Resident File Detector
===================================================================

Purpose: Determines whether NTFS files are resident (stored within MFT records) or 
non-resident (stored in separate disk clusters). This is crucial for forensic analysis
as resident files have different recovery and analysis characteristics.

Key Concepts:
- Resident Files: Small files (typically <1KB) stored directly in MFT records
- Non-Resident Files: Larger files stored in separate clusters with extent mapping
- Cluster Allocation: Method to detect residency by checking for cluster mappings

Features:
- Uses FSCTL_GET_RETRIEVAL_POINTERS for accurate detection
- No administrator privileges required
- Works with all file sizes and types
- Provides detailed file information

Usage: python 04_residency_checker.py [file_path]
Requires: Standard user privileges (no admin required)
"""

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

def safe_handle_close(handle):
    """Safely close a handle if it's valid"""
    if handle and handle != INVALID_HANDLE_VALUE:
        ctypes.windll.kernel32.CloseHandle(handle)

def open_file(path):
    """Open file with proper error handling"""
    try:
        path = f"\\\\?\\{os.path.abspath(path)}"
        handle = ctypes.windll.kernel32.CreateFileW(
            path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        return handle
    except Exception as e:
        raise Exception(f"Failed to open '{path}': {e}")

def check_cluster_allocation(file_handle):
    """
    Check if file has cluster allocations using FSCTL_GET_RETRIEVAL_POINTERS.
    Returns tuple: (has_clusters, extent_info)
    """
    try:
        input_buffer = STARTING_VCN_INPUT_BUFFER(0)
        buffer_size = 4096
        output_buffer = ctypes.create_string_buffer(buffer_size)
        returned = wintypes.DWORD()
        
        result = ctypes.windll.kernel32.DeviceIoControl(
            file_handle, FSCTL_GET_RETRIEVAL_POINTERS,
            ctypes.byref(input_buffer), ctypes.sizeof(input_buffer),
            output_buffer, buffer_size, ctypes.byref(returned), None
        )
        
        if result:
            # API succeeded - file has cluster allocations (non-resident)
            if returned.value >= 16:
                extent_count = int.from_bytes(output_buffer.raw[0:4], "little")
                starting_vcn = int.from_bytes(output_buffer.raw[8:16], "little")
                
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
                return True, {"ExtentCount": 0, "Extents": []}
        else:
            # API failed - check error code
            error_code = ctypes.windll.kernel32.GetLastError()
            if error_code in [ERROR_HANDLE_EOF, ERROR_INVALID_FUNCTION, ERROR_INVALID_USER_BUFFER]:
                return False, None  # No cluster allocations = resident
            else:
                raise ctypes.WinError()
                
    except Exception as e:
        error_code = ctypes.windll.kernel32.GetLastError()
        if error_code in [ERROR_HANDLE_EOF, ERROR_INVALID_FUNCTION, ERROR_INVALID_USER_BUFFER]:
            return False, None
        raise Exception(f"Failed to check cluster allocation: {e}")

def is_file_resident(file_path):
    """
    Determine if a file is resident by checking cluster allocation.
    
    Method: Uses FSCTL_GET_RETRIEVAL_POINTERS to check if file has cluster mappings.
    - Files with cluster allocations = non-resident
    - Files without cluster allocations = resident (data stored in MFT)
    
    Returns True if resident, False if non-resident.
    """
    file_handle = None
    
    try:
        if not os.path.exists(file_path):
            raise Exception(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise Exception(f"Path is not a file: {file_path}")
        
        file_handle = open_file(file_path)
        has_clusters, extent_info = check_cluster_allocation(file_handle)
        
        return not has_clusters  # No clusters = resident
        
    except Exception as e:
        raise Exception(f"Error checking file residency: {e}")
    finally:
        safe_handle_close(file_handle)

def get_detailed_file_info(file_path):
    """Get comprehensive information about a file including residency and cluster details"""
    file_handle = None
    
    try:
        file_handle = open_file(file_path)
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        ):
            raise ctypes.WinError()
        
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        mft_index = file_index & 0xFFFFFFFFFFFF
        sequence_number = (file_index >> 48) & 0xFFFF
        
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
        raise Exception(f"Error getting file information: {e}")
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
            print("Location: Data is embedded within the MFT record itself")
            print("Recovery: Use MFT parsing tools for data extraction")
        else:
            print("Status: NON-RESIDENT (file data stored in clusters on disk)")
            print("Location: Data is stored in separate disk clusters")
            
            if info['extent_info']:
                extent_count = info['extent_info']['ExtentCount']
                print(f"Cluster Extents: {extent_count}")
                
                if info['extent_info']['Extents']:
                    print("Extent details:")
                    for i, extent in enumerate(info['extent_info']['Extents'][:5]):
                        if extent['Lcn'] == -1:
                            print(f"  Extent {i+1}: Sparse/Unallocated (VCN {extent['NextVcn']})")
                        else:
                            print(f"  Extent {i+1}: LCN {extent['Lcn']}, VCN {extent['NextVcn']}")
                    
                    if extent_count > 5:
                        print(f"  ... and {extent_count - 5} more extents")
        
        # Provide analysis context
        print("\\nAnalysis Notes:")
        if info['size'] == 0:
            print("- Empty file (0 bytes)")
        elif info['size'] < 512:
            print("- Very small file - likely to be resident")
        elif info['size'] < 1024:
            print("- Small file - may be resident depending on MFT record space")
        else:
            print("- Larger file - typically non-resident")
            
        if info['is_resident'] and info['size'] > 700:
            print("- Unusually large resident file - verify MFT record structure")
            
    except Exception as e:
        print(f"Error: {e}")

def analyze_residency_patterns(file_paths):
    """Analyze residency patterns across multiple files"""
    resident_files = []
    non_resident_files = []
    errors = []
    
    print("Analyzing residency patterns...")
    print("-" * 50)
    
    for file_path in file_paths:
        try:
            info = get_detailed_file_info(file_path)
            if info['is_resident']:
                resident_files.append(info)
            else:
                non_resident_files.append(info)
        except Exception as e:
            errors.append((file_path, str(e)))
    
    print(f"\\nResults Summary:")
    print(f"Resident files: {len(resident_files)}")
    print(f"Non-resident files: {len(non_resident_files)}")
    print(f"Errors: {len(errors)}")
    
    if resident_files:
        sizes = [f['size'] for f in resident_files]
        print(f"\\nResident file sizes: {min(sizes)} - {max(sizes)} bytes (avg: {sum(sizes)//len(sizes)})")
    
    if non_resident_files:
        sizes = [f['size'] for f in non_resident_files]
        print(f"Non-resident file sizes: {min(sizes)} - {max(sizes)} bytes (avg: {sum(sizes)//len(sizes)})")

if __name__ == "__main__":
    print("File Residency Checker - NTFS Resident vs Non-Resident Detector")
    print("=" * 70)
    print("Uses cluster allocation method - No admin privileges required")
    print()
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print_file_info(file_path)
    else:
        while True:
            try:
                path = input("Enter NTFS file path (or 'quit' to exit): ").strip().strip('"')
                if path.lower() in ['quit', 'exit', 'q']:
                    break
                if path:
                    print()
                    print_file_info(path)
                    print()
            except KeyboardInterrupt:
                print("\\nExiting...")
                break
            except EOFError:
                break

    # Test with some common files to demonstrate
    print("\\n" + "=" * 50)
    print("Testing with common system files:")
    test_files = [
        "C:\\Windows\\win.ini",
        "C:\\Windows\\System32\\drivers\\etc\\hosts"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\\n{'-' * 30}")
            print_file_info(test_file)
        else:
            print(f"Test file not found: {test_file}")