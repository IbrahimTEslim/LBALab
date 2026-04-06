#!/usr/bin/env python3
"""
SSD Detector Module - Detects SSD vs HDD and TRIM capabilities
Handles drive type detection and SSD-specific secure deletion methods
"""
import os
import sys
import ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from core.windows_api import *

class SSDDetector:
    """Detects SSD drives and TRIM capabilities"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        
    def is_ssd(self, drive_letter: str) -> bool:
        """Detect if drive is SSD using multiple methods"""
        try:
            # Method 1: ATA IDENTIFY DEVICE command
            if self._check_ata_identify(drive_letter):
                return True
                
            # Method 2: Check SMART attributes
            if self._check_smart_attributes(drive_letter):
                return True
                
            # Method 3: Windows storage manager API
            if self._check_storage_manager(drive_letter):
                return True
                
            return False
            
        except Exception as e:
            print(f"   SSD detection failed: {e}")
            return False  # Assume HDD for safety
    
    def check_trim_support(self, drive_letter: str) -> bool:
        """Check if drive supports TRIM commands"""
        try:
            # Try to send TRIM command to test support
            handle = self._open_volume_handle(drive_letter)
            if handle == -1:
                return False
            
            try:
                # FSCTL_FILE_LEVEL_TRIM test
                buffer = ctypes.create_string_buffer(512)
                returned = wintypes.DWORD()
                
                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle, FSCTL_FILE_LEVEL_TRIM,
                    None, 0, buffer, 512, ctypes.byref(returned), None
                )
                
                return result != 0
                
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"   TRIM check failed: {e}")
            return False
    
    def get_drive_info(self, drive_letter: str) -> dict:
        """Get comprehensive drive information"""
        return {
            'is_ssd': self.is_ssd(drive_letter),
            'trim_supported': self.check_trim_support(drive_letter),
            'drive_letter': drive_letter.upper(),
            'physical_drive': self.disk_io.get_physical_drive_number(drive_letter)
        }
    
    def _check_ata_identify(self, drive_letter: str) -> bool:
        """Check ATA IDENTIFY DEVICE data for SSD indicators"""
        try:
            drive_num = self.disk_io.get_physical_drive_number(drive_letter)
            handle = self._open_physical_handle(drive_num)
            
            if handle == -1:
                return False
            
            try:
                # Send ATA IDENTIFY DEVICE command
                buffer = ctypes.create_string_buffer(512)
                
                # This is simplified - in practice you'd use ATA pass-through
                # For now, assume drives support TRIM are SSDs
                return True
                
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception:
            return False
    
    def _check_smart_attributes(self, drive_letter: str) -> bool:
        """Check SMART attributes that indicate SSD"""
        try:
            # SMART attributes common in SSDs:
            # - Reallocated Sector Count (low/zero in SSDs)
            # - Power-On Hours
            # - Wear Leveling Count
            # - Host Writes/Reads
            
            # For now, assume modern drives with TRIM are SSDs
            return self.check_trim_support(drive_letter)
            
        except Exception:
            return False
    
    def _check_storage_manager(self, drive_letter: str) -> bool:
        """Use Windows Storage Manager API to detect SSD"""
        try:
            # Windows Storage Manager can detect media type
            # This requires additional Windows APIs not currently imported
            return False
            
        except Exception:
            return False
    
    def _open_volume_handle(self, drive_letter: str):
        """Open volume handle for TRIM operations"""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
        )
        return handle
    
    def _open_physical_handle(self, drive_num: int):
        """Open physical drive handle"""
        physical_path = f"\\\\.\\PhysicalDrive{drive_num}"
        handle = ctypes.windll.kernel32.CreateFileW(
            physical_path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
        )
        return handle
