#!/usr/bin/env python3
"""
MFT Destroyer Module - MFT record corruption and mirror destruction
Handles MFT record location, corruption, and mirror elimination
"""
import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from core.windows_api import *
from modules import LBAReader

class MFTDestroyer:
    """Handles MFT record corruption and mirror destruction"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        
        print(f" MFTDestroyer initialized")
    
    def corrupt_mft_record(self, structure: dict) -> bool:
        """Corrupt and destroy MFT record"""
        print(f"\n Phase 2: MFT Record Corruption")
        
        try:
            drive_letter = structure['drive_letter']
            mft_record_num = structure['mft_record']
            
            print(f" Target: MFT Record {mft_record_num} on {drive_letter}:")
            
            # Get physical drive number
            drive_num = self._get_physical_drive_number(drive_letter)
            
            # Find MFT record location
            mft_lba = self.find_mft_record_lba(drive_letter, mft_record_num)
            if mft_lba is None:
                print(f" Could not locate MFT record {mft_record_num}")
                return False
            
            print(f" MFT Record {mft_record_num} at LBA {mft_lba:,}")
            
            # Create corruption patterns
            corruption_patterns = [
                b'\x00' * 1024,                    # Zero out completely
                b'\xFF' * 1024,                    # All ones
                b'\xBA\xAD\xF0\x0D' * 256,          # BAD_FOOD pattern
                b'\xDE\xAD\xBE\xEF' * 256,          # DEAD_BEEF pattern
                b'ERASED_FILE_RECORD' + b'\x00' * 987,  # Text marker
                os.urandom(1024),                   # Random corruption
            ]
            
            # Apply multiple corruption passes
            for i, pattern in enumerate(corruption_patterns):
                print(f"   Corruption pass {i + 1}/{len(corruption_patterns)}")
                
                try:
                    # Overwrite MFT record using volume write
                    self.disk_io.write_lba_volume(drive_letter, mft_lba, pattern)
                    print(f"    MFT record corrupted with pattern {i + 1}")
                    
                    # Also corrupt the next sector (MFT records can span multiple sectors)
                    self.disk_io.write_lba_volume(drive_letter, mft_lba + 1, pattern)
                    
                except Exception as e:
                    print(f"    Failed to corrupt MFT record: {e}")
                    return False
            
            print(f" MFT Record {mft_record_num} destroyed")
            return True
            
        except Exception as e:
            print(f" MFT corruption failed: {e}")
            return False
    
    def destroy_mft_mirror(self, structure: dict) -> bool:
        """Destroy MFT mirror and backup records"""
        print(f"\n Phase 3: MFT Mirror Destruction")
        
        try:
            drive_letter = structure['drive_letter']
            mft_record_num = structure['mft_record']
            
            print(f" Target: MFT Mirror for Record {mft_record_num}")
            
            # Find MFT mirror location
            mirror_lba = self.find_mft_mirror_record_lba(drive_letter, mft_record_num)
            if mirror_lba is None:
                print(f"  MFT mirror not found (may not exist)")
                return True  # Not a failure
            
            print(f" MFT Mirror at LBA {mirror_lba:,}")
            
            drive_num = self._get_physical_drive_number(drive_letter)
            
            # Destroy mirror with maximum prejudice
            destruction_pattern = b'\xFF' * 1024  # Complete overwrite
            
            try:
                self.disk_io.write_lba_volume(drive_letter, mirror_lba, destruction_pattern)
                self.disk_io.write_lba_volume(drive_letter, mirror_lba + 1, destruction_pattern)
                print(f" MFT Mirror destroyed")
                return True
                
            except Exception as e:
                print(f" Failed to destroy MFT mirror: {e}")
                return False
                
        except Exception as e:
            print(f" MFT mirror destruction failed: {e}")
            return False
    
    def find_mft_record_lba(self, drive_letter: str, record_num: int) -> Optional[int]:
        """Find LBA of specific MFT record"""
        try:
            print(f" Locating MFT Record {record_num} on {drive_letter}:")
            
            # Get volume handle
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
            )
            
            if handle == -1:
                print(f" Cannot open volume {drive_letter}:")
                return None
            
            try:
                # Get MFT location using $Volume information
                buffer = ctypes.create_string_buffer(1024)
                returned = wintypes.DWORD()
                
                # IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS to find disk
                if ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                    None, 0, buffer, 1024, ctypes.byref(returned), None
                ):
                    # Parse to get disk number
                    disk_number = int.from_bytes(buffer[8:12], 'little')
                    print(f" Volume {drive_letter}: on PhysicalDrive{disk_number}")
                    
                    # Now we need to find MFT location
                    # This is complex - we'll use a simplified approach
                    # In practice, you'd parse the $Boot sector to find $MFT
                    
                    # For now, use a heuristic-based approach
                    # MFT typically starts around LBA 0x4000-0x8000 on most systems
                    mft_base_lba = self.find_mft_base_lba(drive_letter)
                    if mft_base_lba is None:
                        print(f" Could not locate MFT base")
                        return None
                    
                    # Calculate record location
                    # MFT records are typically 1024 bytes each
                    record_lba = mft_base_lba + (record_num * 2)  # 2 sectors per record
                    print(f" MFT Record {record_num} estimated at LBA {record_lba:,}")
                    
                    return record_lba
                
                else:
                    print(f" Failed to get volume extents")
                    return None
                    
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f" Failed to find MFT record: {e}")
            return None
    
    def find_mft_base_lba(self, drive_letter: str) -> Optional[int]:
        """Find the base LBA of the MFT"""
        try:
            print(f" Locating MFT base on {drive_letter}:")
            
            # Read boot sector to find MFT location
            boot_sector = self.reader.read_volume(drive_letter, 0, 512)
            
            # Parse NTFS boot sector
            # MFT cluster number is at offset 0x30 (48) for NTFS
            if len(boot_sector) >= 80:
                mft_cluster = int.from_bytes(boot_sector[48:56], 'little')
                sectors_per_cluster = boot_sector[13]
                
                mft_lba = mft_cluster * sectors_per_cluster
                print(f" MFT base found: LBA {mft_lba:,} (cluster {mft_cluster})")
                
                return mft_lba
            else:
                print(f" Invalid boot sector")
                return None
                
        except Exception as e:
            print(f" Failed to find MFT base: {e}")
            # Fallback to common locations
            common_locations = [0x4000, 0x6000, 0x8000, 0x10000]
            for lba in common_locations:
                try:
                    data = self.reader.read_volume(drive_letter, lba, 512)
                    # Check if this looks like MFT (starts with 'FILE')
                    if data[:4] == b'FILE':
                        print(f" MFT found at common location: LBA {lba:,}")
                        return lba
                except:
                    continue
            return None
    
    def find_mft_mirror_record_lba(self, drive_letter: str, record_num: int) -> Optional[int]:
        """Find LBA of MFT mirror record"""
        try:
            print(f" Locating MFT Mirror for Record {record_num} on {drive_letter}:")
            
            # MFT mirror is typically at the end of the volume
            # We need to find volume size first
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
            )
            
            if handle == -1:
                print(f" Cannot open volume {drive_letter}:")
                return None
            
            try:
                # Get volume size
                file_size = ctypes.c_longlong(0)
                if ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(file_size)):
                    total_bytes = file_size.value
                    total_sectors = total_bytes // 512
                    
                    # MFT mirror is typically in the last 25% of the volume
                    mirror_search_start = int(total_sectors * 0.75)
                    
                    print(f" Searching for MFT mirror in LBA range {mirror_search_start:,}-{total_sectors:,}")
                    
                    # Search for MFT mirror (look for 'FILE' signature)
                    search_step = 1000  # Search every 1000 sectors
                    for lba in range(mirror_search_start, total_sectors - 100, search_step):
                        try:
                            data = self.reader.read_volume(drive_letter, lba, 512)
                            if data[:4] == b'FILE':
                                # Found potential MFT mirror
                                mirror_lba = lba + (record_num * 2)
                                print(f" MFT Mirror Record {record_num} at LBA {mirror_lba:,}")
                                return mirror_lba
                        except:
                            continue
                    
                    print(f"  MFT mirror not found in expected location")
                    return None
                else:
                    print(f" Cannot get volume size")
                    return None
                    
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f" Failed to find MFT mirror: {e}")
            return None
    
    def _get_physical_drive_number(self, drive_letter: str) -> int:
        """Get physical drive number from drive letter"""
        return self.disk_io.get_physical_drive_number(drive_letter)
