#!/usr/bin/env python3
"""
TRIM Manager Module - Handles SSD TRIM operations
Implements targeted and full drive TRIM commands
"""
import os
import sys
import ctypes
from ctypes import wintypes
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from core.windows_api import *

class TRIMManager:
    """Handles SSD TRIM operations"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        
        print(f"TRIMManager initialized")
    
    def send_targeted_trim(self, drive_letter: str, lba_ranges: List[Tuple[int, int]]) -> bool:
        """Send TRIM commands for specific LBA ranges"""
        try:
            handle = self._open_volume_handle(drive_letter)
            if handle == -1:
                return False
            
            try:
                for start_lba, length in lba_ranges:
                    # Create TRIM command structure
                    trim_range = self._create_trim_range(start_lba, length)
                    
                    # Send FSCTL_FILE_LEVEL_TRIM
                    result = ctypes.windll.kernel32.DeviceIoControl(
                        handle, FSCTL_FILE_LEVEL_TRIM,
                        trim_range, len(trim_range), None, 0, None, None
                    )
                    
                    if result:
                        print(f"      TRIM sent for LBA {start_lba:,}-{start_lba + length:,}")
                    else:
                        print(f"      TRIM failed for LBA {start_lba:,}")
                
                return True
                
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"      TRIM command error: {e}")
            return False
    
    def send_full_trim(self, drive_letter: str) -> bool:
        """Send TRIM command for entire drive"""
        try:
            handle = self._open_volume_handle(drive_letter)
            if handle == -1:
                return False
            
            try:
                # Create TRIM range for entire drive
                drive_size = self._get_drive_size(drive_letter)
                trim_range = self._create_trim_range(0, drive_size // 512)
                
                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle, FSCTL_FILE_LEVEL_TRIM,
                    trim_range, len(trim_range), None, 0, None, None
                )
                
                if result:
                    print("      Full drive TRIM sent successfully")
                else:
                    print("      Full drive TRIM failed")
                
                return result
                
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"      Full TRIM error: {e}")
            return False
    
    def _create_trim_range(self, start_lba: int, length: int) -> bytes:
        """Create TRIM command structure"""
        # Simplified TRIM structure
        # In practice, this would be a proper DEVICE_MANAGE_DATA_SET_ATTRIBUTES structure
        return start_lba.to_bytes(8, 'little') + length.to_bytes(8, 'little')
    
    def _get_drive_size(self, drive_letter: str) -> int:
        """Get total drive size in bytes"""
        try:
            handle = self._open_volume_handle(drive_letter)
            if handle == -1:
                return 0
            
            try:
                # Get disk geometry
                buffer = ctypes.create_string_buffer(1024)
                returned = wintypes.DWORD()
                
                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_DISK_GET_DRIVE_GEOMETRY,
                    None, 0, buffer, 1024, ctypes.byref(returned), None
                )
                
                if result:
                    # Parse geometry to get size
                    # This is simplified - in practice you'd parse DISK_GEOMETRY
                    return 1024 * 1024 * 1024  # 1GB placeholder
                
                return 0
                
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception:
            return 0
    
    def _open_volume_handle(self, drive_letter: str):
        """Open volume handle for operations"""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
        )
        return handle
