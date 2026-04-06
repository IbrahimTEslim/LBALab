#!/usr/bin/env python3
"""
File Analyzer - Comprehensive file information and analysis
Can be run standalone or imported
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI
from core.ntfs_structures import *
import ctypes
from ctypes import wintypes

class FileAnalyzer:
    """Analyze NTFS files and get comprehensive information"""
    
    def __init__(self):
        self.disk_io = DiskIO()
    
    def get_file_info(self, file_path):
        """Get file information including MFT record number"""
        handle = self.disk_io.open_file(file_path)
        try:
            file_info = BY_HANDLE_FILE_INFORMATION()
            if not ctypes.windll.kernel32.GetFileInformationByHandle(handle, ctypes.byref(file_info)):
                raise OSError("GetFileInformationByHandle failed")
            
            file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
            mft_record_number = file_index & 0xFFFFFFFFFFFF
            sequence_number = (file_index >> 48) & 0xFFFF
            
            return {
                "file_index": file_index,
                "mft_record_number": mft_record_number,
                "sequence_number": sequence_number,
                "volume_serial": file_info.dwVolumeSerialNumber,
                "file_size": (file_info.nFileSizeHigh << 32) | file_info.nFileSizeLow,
                "attributes": file_info.dwFileAttributes,
                "link_count": file_info.nNumberOfLinks
            }
        finally:
            WindowsAPI.close_handle(handle)
    
    def get_volume_info(self, drive_letter):
        """Get NTFS volume information"""
        handle = self.disk_io.open_volume(drive_letter)
        try:
            vol_info = NTFS_VOLUME_DATA_BUFFER()
            returned = wintypes.DWORD()
            
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, 0x90064, None, 0,  # FSCTL_GET_NTFS_VOLUME_DATA
                ctypes.byref(vol_info), ctypes.sizeof(vol_info),
                ctypes.byref(returned), None
            ):
                raise OSError("DeviceIoControl failed")
            
            return {
                'volume_serial': vol_info.VolumeSerialNumber,
                'bytes_per_sector': vol_info.BytesPerSector,
                'bytes_per_cluster': vol_info.BytesPerCluster,
                'mft_start_lcn': vol_info.MftStartLcn,
                'mft_record_size': vol_info.BytesPerFileRecordSegment,
                'total_clusters': vol_info.TotalClusters,
                'free_clusters': vol_info.FreeClusters
            }
        finally:
            WindowsAPI.close_handle(handle)
    
    def get_partition_start_lba(self, drive_letter):
        """Get partition starting LBA"""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, 0, 1, None, 3, 0, None  # FILE_SHARE_READ, OPEN_EXISTING
        )
        if handle == -1:
            raise OSError(f"Cannot open volume {drive_letter}")
        
        try:
            part_info = PARTITION_INFORMATION_EX()
            returned = wintypes.DWORD()
            
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, 0x00070048, None, 0,  # IOCTL_DISK_GET_PARTITION_INFO_EX
                ctypes.byref(part_info), ctypes.sizeof(part_info),
                ctypes.byref(returned), None
            ):
                raise OSError("DeviceIoControl failed")
            
            return part_info.StartingOffset // 512
        finally:
            WindowsAPI.close_handle(handle)
    
    def get_sectors_per_cluster(self, drive_letter):
        """Get sectors per cluster"""
        sectors_per_cluster = wintypes.DWORD()
        bytes_per_sector = wintypes.DWORD()
        free_clusters = wintypes.DWORD()
        total_clusters = wintypes.DWORD()
        
        if not ctypes.windll.kernel32.GetDiskFreeSpaceW(
            ctypes.c_wchar_p(drive_letter + ":\\\\"),
            ctypes.byref(sectors_per_cluster), ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters), ctypes.byref(total_clusters)
        ):
            raise OSError("GetDiskFreeSpaceW failed")
        
        return sectors_per_cluster.value, bytes_per_sector.value

def main():
    """Standalone CLI"""
    if not WindowsAPI.is_admin():
        print("  Run as Administrator")
        return 1
    
    if len(sys.argv) < 2:
        print("Usage: file_analyzer.py <file_path>")
        return 1
    
    analyzer = FileAnalyzer()
    file_path = sys.argv[1]
    
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return 1
        
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        
        print(f"Analyzing: {file_path}")
        print("=" * 60)
        
        # File info
        file_info = analyzer.get_file_info(file_path)
        print("\n=== File Information ===")
        print(f"MFT Record Number: {file_info['mft_record_number']:,}")
        print(f"Sequence Number: {file_info['sequence_number']}")
        print(f"File Size: {file_info['file_size']:,} bytes")
        print(f"Link Count: {file_info['link_count']}")
        
        # Volume info
        vol_info = analyzer.get_volume_info(drive_letter)
        print("\n=== Volume Information ===")
        print(f"Bytes per Sector: {vol_info['bytes_per_sector']}")
        print(f"Bytes per Cluster: {vol_info['bytes_per_cluster']}")
        print(f"MFT Start LCN: {vol_info['mft_start_lcn']:,}")
        print(f"MFT Record Size: {vol_info['mft_record_size']} bytes")
        
        # Partition info
        partition_lba = analyzer.get_partition_start_lba(drive_letter)
        print(f"\n=== Partition Information ===")
        print(f"Partition Start LBA: {partition_lba:,}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
