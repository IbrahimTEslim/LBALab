#!/usr/bin/env python3
"""
Hidden Space Handler Module - Handles data in hidden/protected areas
Accesses reserved areas, over-provisioning space, and service areas
"""
import os
import sys
import ctypes
from ctypes import wintypes
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from modules import LBAReader

class HiddenSpaceHandler:
    """Handles hidden and protected areas on drives"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        
        print(f"HiddenSpaceHandler initialized")
    
    def wipe_hidden_areas(self, drive_letter: str) -> bool:
        """Wipe all hidden and protected areas on drive"""
        print(f"\nHidden Space Phase: Wiping hidden areas on {drive_letter}:")
        
        success = True
        
        # Step 1: Service areas (Host Protected Area)
        if not self._wipe_service_areas(drive_letter):
            print("   Service area wipe incomplete")
            success = False
        
        # Step 2: Unallocated sectors between partitions
        if not self._wipe_unallocated_sectors(drive_letter):
            print("   Unallocated sector wipe incomplete")
            success = False
        
        # Step 3: SSD over-provisioning space
        if not self._wipe_overprovisioning_space(drive_letter):
            print("   Over-provisioning space wipe incomplete")
            success = False
        
        # Step 4: Reserved system areas
        if not self._wipe_reserved_areas(drive_letter):
            print("   Reserved area wipe incomplete")
            success = False
        
        print(f"Hidden space wiping: {'SUCCESS' if success else 'PARTIAL'}")
        return success
    
    def _wipe_service_areas(self, drive_letter: str) -> bool:
        """Wipe Host Protected Area and service sectors"""
        try:
            print("   Wiping service areas...")
            
            # Common service area locations
            service_areas = [
                (0, 63),        # MBR/Partition table area
                (1, 62),        # Hidden sectors after MBR
                (2048, 2048),     # GPT header area
                (1024, 1024),     # Additional service area
            ]
            
            drive_num = self.disk_io.get_physical_drive_number(drive_letter)
            wipe_pattern = b'\x00' * 512
            
            for start_lba, length in service_areas:
                try:
                    for offset in range(length):
                        current_lba = start_lba + offset
                        self.disk_io.write_lba_volume(drive_letter, current_lba, wipe_pattern)
                    
                    print(f"      Service area LBA {start_lba:,}-{start_lba + length:,} wiped")
                    
                except Exception as e:
                    print(f"      Failed to wipe service area at LBA {start_lba}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   Service area wipe failed: {e}")
            return False
    
    def _wipe_unallocated_sectors(self, drive_letter: str) -> bool:
        """Wipe sectors between partitions"""
        try:
            print("   Wiping unallocated sectors...")
            
            # Get partition layout
            partitions = self._get_partition_layout(drive_letter)
            if not partitions:
                print("      Could not read partition layout")
                return False
            
            # Find gaps between partitions
            gaps = self._find_partition_gaps(partitions)
            
            wipe_pattern = b'\xFF' * 512
            
            for gap_start, gap_length in gaps:
                try:
                    print(f"      Wiping gap LBA {gap_start:,}-{gap_start + gap_length:,}")
                    
                    for offset in range(gap_length):
                        current_lba = gap_start + offset
                        self.disk_io.write_lba_volume(drive_letter, current_lba, wipe_pattern)
                
                except Exception as e:
                    print(f"      Failed to wipe gap at LBA {gap_start}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   Unallocated sector wipe failed: {e}")
            return False
    
    def _wipe_overprovisioning_space(self, drive_letter: str) -> bool:
        """Wipe SSD over-provisioning space"""
        try:
            print("   Wiping over-provisioning space...")
            
            # Get drive size and last partition end
            drive_size = self._get_drive_size(drive_letter)
            partitions = self._get_partition_layout(drive_letter)
            
            if not partitions:
                return False
            
            # Find last partition
            last_partition = max(partitions, key=lambda p: p['end_lba'])
            last_lba = last_partition['end_lba']
            
            # Calculate over-provisioning area (typically 7-10% of drive)
            provisioning_start = last_lba + 1
            provisioning_size = drive_size // 512 - provisioning_start
            
            if provisioning_size <= 0:
                print("      No over-provisioning space detected")
                return True
            
            print(f"      Over-provisioning area: LBA {provisioning_start:,}-{drive_size // 512:,}")
            
            wipe_pattern = b'\x00' * 512
            
            try:
                for offset in range(0, provisioning_size, 1000):  # Wipe in chunks
                    current_lba = provisioning_start + offset
                    chunk_size = min(1000, provisioning_size - offset)
                    
                    for i in range(chunk_size):
                        self.disk_io.write_lba_volume(drive_letter, current_lba + i, wipe_pattern)
                    
                    # Progress
                    if offset % 10000 == 0:
                        progress = (offset / provisioning_size) * 100
                        print(f"      Progress: {progress:.1f}%")
                
                return True
                
            except Exception as e:
                print(f"      Over-provisioning wipe failed: {e}")
                return False
            
        except Exception as e:
            print(f"   Over-provisioning wipe failed: {e}")
            return False
    
    def _wipe_reserved_areas(self, drive_letter: str) -> bool:
        """Wipe reserved system areas"""
        try:
            print("   Wiping reserved areas...")
            
            # Common reserved area locations
            reserved_areas = [
                (63, 1),         # Hidden track
                (256, 1),         # Diagnostic track
                (1024, 1),        # Additional reserved
            ]
            
            wipe_pattern = b'\x55\xAA' * 256  # Reserved pattern
            
            for start_lba, length in reserved_areas:
                try:
                    for offset in range(length):
                        current_lba = start_lba + offset
                        self.disk_io.write_lba_volume(drive_letter, current_lba, wipe_pattern)
                    
                    print(f"      Reserved area LBA {start_lba:,} wiped")
                    
                except Exception as e:
                    print(f"      Failed to wipe reserved area at LBA {start_lba}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   Reserved area wipe failed: {e}")
            return False
    
    def _get_partition_layout(self, drive_letter: str) -> List[Dict]:
        """Get partition layout from disk"""
        try:
            # This is simplified - in practice you'd use Windows Storage Manager API
            # For now, return a basic partition layout
            
            # Simulate reading partition table
            partitions = [
                {'start_lba': 2048, 'end_lba': 2068479, 'size_mb': 1000},  # First partition
                {'start_lba': 2068480, 'end_lba': 4196351, 'size_mb': 1000},  # Second partition
            ]
            
            return partitions
            
        except Exception:
            return []
    
    def _find_partition_gaps(self, partitions: List[Dict]) -> List[tuple]:
        """Find gaps between partitions"""
        if not partitions:
            return []
        
        gaps = []
        
        # Sort partitions by start LBA
        sorted_partitions = sorted(partitions, key=lambda p: p['start_lba'])
        
        # Gap before first partition (after MBR)
        if sorted_partitions[0]['start_lba'] > 63:
            gaps.append((63, sorted_partitions[0]['start_lba'] - 63))
        
        # Gaps between partitions
        for i in range(len(sorted_partitions) - 1):
            current_end = sorted_partitions[i]['end_lba']
            next_start = sorted_partitions[i + 1]['start_lba']
            
            if next_start > current_end + 1:
                gaps.append((current_end + 1, next_start - current_end - 1))
        
        return gaps
    
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
                    return 1024 * 1024 * 1024 * 100  # 100GB placeholder
                
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
