#!/usr/bin/env python3
"""
Windows File Block Locator and Writer
Finds the exact disk blocks a file occupies and writes configurable data above them.

WARNING: This script performs low-level disk operations and requires Administrator privileges.
Use with extreme caution as it can corrupt data if misused.
"""

import os
import sys
import ctypes
from ctypes import wintypes, byref, sizeof, Structure, Union, POINTER
from ctypes.wintypes import DWORD, LARGE_INTEGER, HANDLE, BOOL
import struct

# Windows API constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = -1

# IOCTL codes for FSCTL_GET_RETRIEVAL_POINTERS
FSCTL_GET_RETRIEVAL_POINTERS = 0x00090073

# Error codes
ERROR_MORE_DATA = 234
ERROR_HANDLE_EOF = 38

class RETRIEVAL_POINTERS_BUFFER(Structure):
    """Structure for file extent information"""
    _fields_ = [
        ('ExtentCount', DWORD),
        ('StartingVcn', LARGE_INTEGER),
    ]

class EXTENT(Structure):
    """Individual extent structure"""
    _fields_ = [
        ('NextVcn', LARGE_INTEGER),
        ('Lcn', LARGE_INTEGER),
    ]

class STARTING_VCN_INPUT_BUFFER(Structure):
    """Input buffer for retrieval pointers"""
    _fields_ = [
        ('StartingVcn', LARGE_INTEGER),
    ]

# Windows API functions
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, DWORD, DWORD, ctypes.c_void_p,
    DWORD, DWORD, HANDLE
]
kernel32.CreateFileW.restype = HANDLE

kernel32.DeviceIoControl.argtypes = [
    HANDLE, DWORD, ctypes.c_void_p, DWORD,
    ctypes.c_void_p, DWORD, POINTER(DWORD), ctypes.c_void_p
]
kernel32.DeviceIoControl.restype = BOOL

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.GetLastError.restype = DWORD

class WindowsFileBlockWriter:
    def __init__(self):
        self.cluster_size = 4096  # Default cluster size (4KB)
        self.bytes_per_sector = 512  # Default sector size
        
    def is_admin(self):
        """Check if running with Administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def get_volume_info(self, drive_letter):
        """Get volume information including cluster size"""
        try:
            sectors_per_cluster = wintypes.DWORD()
            bytes_per_sector = wintypes.DWORD()
            free_clusters = wintypes.DWORD()
            total_clusters = wintypes.DWORD()
            
            success = kernel32.GetDiskFreeSpaceW(
                drive_letter,
                byref(sectors_per_cluster),
                byref(bytes_per_sector),
                byref(free_clusters),
                byref(total_clusters)
            )
            
            if success:
                self.cluster_size = sectors_per_cluster.value * bytes_per_sector.value
                self.bytes_per_sector = bytes_per_sector.value
                return True
            return False
        except Exception as e:
            print(f"Error getting volume info: {e}")
            return False
    
    def get_file_extents(self, filepath):
        """
        Get the physical disk clusters where the file is stored using NTFS.
        Returns list of extent information.
        """
        try:
            # Open the file
            file_handle = kernel32.CreateFileW(
                filepath,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            if file_handle == INVALID_HANDLE_VALUE:
                error = kernel32.GetLastError()
                print(f"Error opening file: {error}")
                return []
            
            try:
                extents = []
                start_vcn = 0
                
                while True:
                    # Prepare input buffer
                    input_buffer = STARTING_VCN_INPUT_BUFFER()
                    input_buffer.StartingVcn = start_vcn
                    
                    # Prepare output buffer (large enough for multiple extents)
                    buffer_size = 1024 * 64  # 64KB buffer
                    output_buffer = ctypes.create_string_buffer(buffer_size)
                    bytes_returned = DWORD()
                    
                    # Call FSCTL_GET_RETRIEVAL_POINTERS
                    success = kernel32.DeviceIoControl(
                        file_handle,
                        FSCTL_GET_RETRIEVAL_POINTERS,
                        byref(input_buffer),
                        sizeof(input_buffer),
                        output_buffer,
                        buffer_size,
                        byref(bytes_returned),
                        None
                    )
                    
                    error = kernel32.GetLastError()
                    
                    if not success and error != ERROR_MORE_DATA:
                        if error == ERROR_HANDLE_EOF:
                            break  # No more extents
                        print(f"DeviceIoControl failed with error: {error}")
                        break
                    
                    if bytes_returned.value < sizeof(RETRIEVAL_POINTERS_BUFFER):
                        break
                    
                    # Parse the output buffer
                    retrieval_buffer = ctypes.cast(output_buffer, POINTER(RETRIEVAL_POINTERS_BUFFER)).contents
                    extent_count = retrieval_buffer.ExtentCount
                    starting_vcn = retrieval_buffer.StartingVcn
                    
                    # Calculate offset to extents array
                    extents_offset = sizeof(RETRIEVAL_POINTERS_BUFFER)
                    
                    for i in range(extent_count):
                        extent_ptr = ctypes.cast(
                            ctypes.addressof(output_buffer) + extents_offset + i * sizeof(EXTENT),
                            POINTER(EXTENT)
                        ).contents
                        
                        extent_info = {
                            'vcn_start': starting_vcn if i == 0 else extents[-1]['vcn_end'],
                            'vcn_end': extent_ptr.NextVcn,
                            'lcn': extent_ptr.Lcn,
                            'length_clusters': extent_ptr.NextVcn - (starting_vcn if i == 0 else extents[-1]['vcn_end']),
                            'physical_offset': extent_ptr.Lcn * self.cluster_size,
                            'length_bytes': (extent_ptr.NextVcn - (starting_vcn if i == 0 else extents[-1]['vcn_end'])) * self.cluster_size
                        }
                        
                        extents.append(extent_info)
                    
                    # Check if we need to continue
                    if not success and error == ERROR_MORE_DATA:
                        # Continue from the last VCN
                        start_vcn = extents[-1]['vcn_end']
                    else:
                        break
                
                return extents
                
            finally:
                kernel32.CloseHandle(file_handle)
                
        except Exception as e:
            print(f"Error getting file extents: {e}")
            return []
    
    def get_drive_letter(self, filepath):
        """Extract drive letter from file path"""
        abs_path = os.path.abspath(filepath)
        return abs_path[:3]  # e.g., "C:\"
    
    def get_physical_drive(self, drive_letter):
        """Get physical drive path for the given drive letter"""
        # Remove the backslash if present
        drive = drive_letter.rstrip('\\')
        
        # For now, assume simple mapping (this could be enhanced to query actual physical drive)
        drive_num = ord(drive[0].upper()) - ord('A')
        return f"\\\\.\\PhysicalDrive{drive_num}"
    
    def write_above_blocks(self, filepath, data_to_write, offset_clusters=1):
        """
        Write data above the file's clusters on disk.
        
        Args:
            filepath: Path to the file
            data_to_write: Bytes to write
            offset_clusters: Number of clusters above the file to write (default: 1)
        """
        if not os.path.exists(filepath):
            print(f"Error: File {filepath} does not exist")
            return False
        
        if not self.is_admin():
            print("Error: This operation requires Administrator privileges")
            return False
        
        print(f"Analyzing file: {filepath}")
        
        # Get drive info
        drive_letter = self.get_drive_letter(filepath)
        if not self.get_volume_info(drive_letter):
            print("Could not get volume information")
            return False
        
        print(f"Cluster size: {self.cluster_size} bytes")
        
        # Get file extents
        extents = self.get_file_extents(filepath)
        if not extents:
            print("Could not get file extents")
            return False
        
        print(f"Found {len(extents)} extent(s)")
        for i, extent in enumerate(extents):
            print(f"  Extent {i+1}: LCN {extent['lcn']}, "
                  f"Length {extent['length_clusters']} clusters "
                  f"({extent['length_bytes']} bytes)")
        
        # Get physical drive path
        physical_drive = self.get_physical_drive(drive_letter)
        print(f"Physical drive: {physical_drive}")
        
        try:
            # Open physical drive for writing
            drive_handle = kernel32.CreateFileW(
                physical_drive,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            
            if drive_handle == INVALID_HANDLE_VALUE:
                error = kernel32.GetLastError()
                print(f"Error opening physical drive: {error}")
                return False
            
            try:
                for i, extent in enumerate(extents):
                    if extent['lcn'] <= 0:  # Skip sparse or compressed extents
                        print(f"Skipping extent {i+1} (sparse/compressed)")
                        continue
                    
                    # Calculate the position above this extent
                    extent_start_cluster = extent['lcn']
                    target_cluster = max(0, extent_start_cluster - offset_clusters)
                    target_offset = target_cluster * self.cluster_size
                    
                    print(f"Writing above extent {i+1}:")
                    print(f"  Extent starts at cluster {extent_start_cluster}")
                    print(f"  Writing at cluster {target_cluster} (offset {target_offset})")
                    
                    # Set file pointer
                    high_part = DWORD(target_offset >> 32)
                    low_part = kernel32.SetFilePointer(
                        drive_handle,
                        target_offset & 0xFFFFFFFF,
                        byref(high_part),
                        0  # FILE_BEGIN
                    )
                    
                    if low_part == 0xFFFFFFFF:
                        error = kernel32.GetLastError()
                        if error != 0:  # NO_ERROR
                            print(f"Error setting file pointer: {error}")
                            continue
                    
                    # Ensure data fits within a cluster
                    write_data = data_to_write[:self.cluster_size]
                    if len(write_data) < self.cluster_size:
                        write_data += b'\x00' * (self.cluster_size - len(write_data))
                    
                    # Read existing data first (for safety)
                    existing_buffer = ctypes.create_string_buffer(self.cluster_size)
                    bytes_read = DWORD()
                    
                    kernel32.ReadFile(
                        drive_handle,
                        existing_buffer,
                        self.cluster_size,
                        byref(bytes_read),
                        None
                    )
                    
                    print(f"  Existing data at target location: {existing_buffer.raw[:50]}...")
                    
                    # Reset file pointer and write
                    high_part = DWORD(target_offset >> 32)
                    kernel32.SetFilePointer(
                        drive_handle,
                        target_offset & 0xFFFFFFFF,
                        byref(high_part),
                        0
                    )
                    
                    write_buffer = ctypes.create_string_buffer(write_data)
                    bytes_written = DWORD()
                    
                    success = kernel32.WriteFile(
                        drive_handle,
                        write_buffer,
                        len(write_data),
                        byref(bytes_written),
                        None
                    )
                    
                    if success:
                        kernel32.FlushFileBuffers(drive_handle)
                        print(f"  Wrote {bytes_written.value} bytes successfully")
                    else:
                        error = kernel32.GetLastError()
                        print(f"  Write failed with error: {error}")
                
                return True
                
            finally:
                kernel32.CloseHandle(drive_handle)
                
        except Exception as e:
            print(f"Error writing to drive: {e}")
            return False
    
    def read_clusters_above_file(self, filepath, offset_clusters=1, read_size=None):
        """
        Read data from clusters above the file's location.
        """
        if read_size is None:
            read_size = self.cluster_size
            
        drive_letter = self.get_drive_letter(filepath)
        self.get_volume_info(drive_letter)
        
        extents = self.get_file_extents(filepath)
        if not extents:
            return None
        
        physical_drive = self.get_physical_drive(drive_letter)
        
        try:
            drive_handle = kernel32.CreateFileW(
                physical_drive,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            
            if drive_handle == INVALID_HANDLE_VALUE:
                return None
            
            try:
                data_blocks = []
                for extent in extents:
                    if extent['lcn'] <= 0:
                        continue
                    
                    extent_start_cluster = extent['lcn']
                    target_cluster = max(0, extent_start_cluster - offset_clusters)
                    target_offset = target_cluster * self.cluster_size
                    
                    # Set file pointer
                    high_part = DWORD(target_offset >> 32)
                    kernel32.SetFilePointer(
                        drive_handle,
                        target_offset & 0xFFFFFFFF,
                        byref(high_part),
                        0
                    )
                    
                    # Read data
                    buffer = ctypes.create_string_buffer(read_size)
                    bytes_read = DWORD()
                    
                    success = kernel32.ReadFile(
                        drive_handle,
                        buffer,
                        read_size,
                        byref(bytes_read),
                        None
                    )
                    
                    if success:
                        data_blocks.append(buffer.raw[:bytes_read.value])
                
                return data_blocks
                
            finally:
                kernel32.CloseHandle(drive_handle)
                
        except Exception as e:
            print(f"Error reading from drive: {e}")
            return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python windows_file_block_writer.py <filepath> [data_to_write]")
        print("Example: python windows_file_block_writer.py C:\\path\\to\\file.txt \"Hello World\"")
        print("\nNOTE: Must be run as Administrator!")
        sys.exit(1)
    
    filepath = sys.argv[1]
    data_to_write = sys.argv[2].encode('utf-8') if len(sys.argv) > 2 else b"MARKER_DATA_FROM_BLOCK_WRITER"
    
    writer = WindowsFileBlockWriter()
    
    if not writer.is_admin():
        print("ERROR: This script must be run as Administrator!")
        print("Right-click Command Prompt and select 'Run as administrator'")
        sys.exit(1)
    
    print("=== Windows File Block Analysis ===")
    
    # Get drive info first
    drive_letter = writer.get_drive_letter(filepath)
    if not writer.get_volume_info(drive_letter):
        print("Could not get volume information")
        sys.exit(1)
    
    extents = writer.get_file_extents(filepath)
    
    if not extents:
        print("Could not analyze file blocks")
        sys.exit(1)
    
    print(f"File: {filepath}")
    print(f"Drive: {drive_letter}")
    print(f"Cluster size: {writer.cluster_size} bytes")
    print(f"Found {len(extents)} extent(s):")
    
    for i, extent in enumerate(extents):
        print(f"  Extent {i+1}:")
        print(f"    VCN range: {extent['vcn_start']} - {extent['vcn_end']}")
        print(f"    LCN: {extent['lcn']}")
        print(f"    Length: {extent['length_clusters']} clusters ({extent['length_bytes']} bytes)")
        print(f"    Physical offset: {extent['physical_offset']} bytes")
    
    # Ask for confirmation before writing
    print(f"\nData to write: {data_to_write}")
    response = input(f"Write data above these blocks? (y/N): ").lower()
    if response == 'y':
        print("\n=== Writing Data ===")
        success = writer.write_above_blocks(filepath, data_to_write)
        if success:
            print("Data written successfully!")
        else:
            print("Failed to write data")
    else:
        print("Operation cancelled")

if __name__ == "__main__":
    main()