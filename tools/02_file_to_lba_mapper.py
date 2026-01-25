#!/usr/bin/env python3
"""
File to LBA Mapper - NTFS File Location Analyzer
===============================================

Purpose: Maps NTFS files to their physical disk locations using VCN → LCN → LBA mapping.
This tool shows exactly where file data is stored on the physical disk by analyzing
NTFS cluster allocation and converting virtual addresses to physical sector addresses.

Key Concepts:
- VCN (Virtual Cluster Number): Logical cluster numbering within a file (0, 1, 2, ...)
- LCN (Logical Cluster Number): Physical cluster number on the NTFS volume
- LBA (Logical Block Address): Physical sector address on the disk

Features:
- File extent mapping and fragmentation analysis
- Partition offset calculation
- Cluster to sector conversion
- Support for sparse files and compressed data

Usage: python 02_file_to_lba_mapper.py
Requires: Administrator privileges for low-level disk access
"""

import ctypes
import os
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3

class STARTING_VCN_INPUT_BUFFER(ctypes.Structure):
    _fields_ = [("StartingVcn", ctypes.c_longlong)]

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

def open_file(path):
    """Open file with proper error handling"""
    path = f"\\\\?\\{os.path.abspath(path)}"
    handle = ctypes.windll.kernel32.CreateFileW(
        path, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None
    )
    if handle == -1:
        raise ctypes.WinError()
    return handle

def get_file_extents(file_handle):
    """Get file extents (VCN → LCN mapping)"""
    input_buffer = STARTING_VCN_INPUT_BUFFER(0)
    out_size = 4096
    output_buffer = ctypes.create_string_buffer(out_size)
    returned = wintypes.DWORD()

    res = ctypes.windll.kernel32.DeviceIoControl(
        file_handle, FSCTL_GET_RETRIEVAL_POINTERS,
        ctypes.byref(input_buffer), ctypes.sizeof(input_buffer),
        output_buffer, out_size, ctypes.byref(returned), None
    )

    if not res:
        err = ctypes.GetLastError()
        if err == 1:  # ERROR_INVALID_FUNCTION - file is resident
            return None
        raise ctypes.WinError(err)

    if returned.value < 16:
        return None
    
    extent_count = int.from_bytes(output_buffer[0:4], 'little')
    starting_vcn = int.from_bytes(output_buffer[8:16], 'little')
    
    extents = []
    current_vcn = starting_vcn
    
    for i in range(extent_count):
        offset = 16 + i * 16
        if offset + 16 > returned.value:
            break
            
        next_vcn = int.from_bytes(output_buffer[offset:offset+8], 'little')
        lcn_raw = output_buffer[offset+8:offset+16]
        
        if lcn_raw == b'\\xff' * 8:
            lcn = -1  # Sparse extent
        else:
            lcn = int.from_bytes(lcn_raw, 'little')
        
        extents.append((current_vcn, next_vcn, lcn))
        current_vcn = next_vcn

    return extents

def get_partition_start_lba(drive_letter):
    """Get partition starting LBA"""
    volume_path = f"\\\\.\\{drive_letter}:"
    handle = ctypes.windll.kernel32.CreateFileW(
        volume_path, 0, 1, None, OPEN_EXISTING, 0, None
    )
    if handle == -1:
        raise ctypes.WinError()

    part_info = PARTITION_INFORMATION_EX()
    returned = wintypes.DWORD()
    
    try:
        res = ctypes.windll.kernel32.DeviceIoControl(
            handle, IOCTL_DISK_GET_PARTITION_INFO_EX, None, 0,
            ctypes.byref(part_info), ctypes.sizeof(part_info),
            ctypes.byref(returned), None
        )
        if not res:
            raise ctypes.WinError()
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

    return part_info.StartingOffset // 512

def get_sectors_per_cluster(drive_letter):
    """Get sectors per cluster and bytes per sector"""
    sectors_per_cluster = wintypes.DWORD()
    bytes_per_sector = wintypes.DWORD()
    free_clusters = wintypes.DWORD()
    total_clusters = wintypes.DWORD()

    res = ctypes.windll.kernel32.GetDiskFreeSpaceW(
        ctypes.c_wchar_p(drive_letter + ":\\\\"),
        ctypes.byref(sectors_per_cluster), ctypes.byref(bytes_per_sector),
        ctypes.byref(free_clusters), ctypes.byref(total_clusters)
    )
    if not res:
        raise ctypes.WinError()

    return sectors_per_cluster.value, bytes_per_sector.value

def analyze_file_mapping(file_path):
    """Analyze file's VCN → LCN → LBA mapping"""
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        return
    
    drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
    
    try:
        # Get disk geometry
        partition_start_lba = get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = get_sectors_per_cluster(drive_letter)
        cluster_size = sectors_per_cluster * bytes_per_sector
        
        print(f"File: {file_path}")
        print(f"Drive: {drive_letter}: (Partition starts at LBA {partition_start_lba:,})")
        print(f"Cluster size: {cluster_size:,} bytes ({sectors_per_cluster} sectors)")
        print()
        
        # Get file extents
        handle = open_file(file_path)
        extents = get_file_extents(handle)
        ctypes.windll.kernel32.CloseHandle(handle)
        
        if extents is None:
            print("File is RESIDENT (data stored inside MFT record)")
            print("No cluster allocation - file data is embedded in the MFT.")
            return
        
        if not extents:
            print("File has no allocated extents (empty file)")
            return
        
        print("File is NON-RESIDENT (data stored in disk clusters)")
        print("\\nVCN → LCN → LBA Mapping:")
        print("-" * 80)
        
        total_clusters = 0
        allocated_clusters = 0
        fragmented = len(extents) > 1
        
        for i, (start_vcn, next_vcn, lcn) in enumerate(extents):
            cluster_count = next_vcn - start_vcn
            total_clusters += cluster_count
            
            if lcn == -1:
                print(f"Extent {i+1:2d}: VCN {start_vcn:8,}-{next_vcn-1:8,} "
                      f"({cluster_count:6,} clusters) → SPARSE (not allocated)")
            else:
                allocated_clusters += cluster_count
                lba = partition_start_lba + (lcn * sectors_per_cluster)
                byte_offset = lba * bytes_per_sector
                size_bytes = cluster_count * cluster_size
                
                print(f"Extent {i+1:2d}: VCN {start_vcn:8,}-{next_vcn-1:8,} "
                      f"({cluster_count:6,} clusters) → LCN {lcn:8,}")
                print(f"           → LBA {lba:12,} → Byte offset {byte_offset:15,}")
                print(f"           → Size: {size_bytes:10,} bytes")
        
        print("-" * 80)
        print(f"Summary:")
        print(f"  Total clusters: {total_clusters:,}")
        print(f"  Allocated clusters: {allocated_clusters:,}")
        print(f"  Sparse clusters: {total_clusters - allocated_clusters:,}")
        print(f"  Total allocated size: {allocated_clusters * cluster_size:,} bytes")
        print(f"  File fragmentation: {'Yes' if fragmented else 'No'} ({len(extents)} extent{'s' if len(extents) != 1 else ''})")
        
        if fragmented:
            print(f"  ⚠️  File is fragmented across {len(extents)} non-contiguous regions")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("File to LBA Mapper - NTFS File Location Analyzer")
    print("=" * 55)
    print("Maps files to their physical disk locations (VCN → LCN → LBA)")
    print()
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        analyze_file_mapping(file_path)
    else:
        while True:
            try:
                file_path = input("Enter NTFS file path (or 'quit' to exit): ").strip().strip('"')
                if file_path.lower() in ['quit', 'exit', 'q']:
                    break
                if file_path:
                    print()
                    analyze_file_mapping(file_path)
                    print()
            except KeyboardInterrupt:
                print("\\nExiting...")
                break
            except EOFError:
                break