#!/usr/bin/env python3
"""
Reference Eliminator Module - Related records and references destruction
Handles directory references, hard links, and security descriptor elimination
"""
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from modules import LBAReader, MFTDestroyer

class ReferenceEliminator:
    """Handles elimination of related records and references"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        self.mft_destroyer = MFTDestroyer(disk_io)
        
        print(f" ReferenceEliminator initialized")
    
    def eliminate_related_records(self, structure: Dict) -> bool:
        """Eliminate all related records and references"""
        print(f"\n Phase 5: Related Records Elimination")
        
        success = True
        
        try:
            drive_letter = structure['drive_letter']
            mft_record = structure['mft_record']
            
            # Find and destroy parent directory references
            print(f"    Eliminating directory references...")
            if not self.eliminate_directory_references(drive_letter, mft_record):
                print(f"     Directory reference elimination incomplete")
                success = False
            
            # Destroy hard link references
            print(f"    Eliminating hard links...")
            if not self.eliminate_hard_links(drive_letter, mft_record):
                print(f"     Hard link elimination incomplete")
                success = False
            
            # Destroy security descriptor references
            print(f"    Eliminating security descriptors...")
            if not self.eliminate_security_references(drive_letter, mft_record):
                print(f"     Security reference elimination incomplete")
                success = False
            
            print(f" Related records elimination complete: {'SUCCESS' if success else 'PARTIAL'}")
            return success
            
        except Exception as e:
            print(f" Related records elimination failed: {e}")
            return False
    
    def eliminate_directory_references(self, drive_letter: str, mft_record: int) -> bool:
        """Eliminate directory references"""
        try:
            print(f"  Eliminating directory references for MFT {mft_record} on {drive_letter}:")
            
            # Directory references are stored in directory indexes ($I30)
            # We need to find and corrupt directory entries that reference our file
            
            # This is complex - we'll corrupt common directory index areas
            index_locations = [
                0x5000,   # Common root directory location
                0x6000,   # Alternative location
                0x7000,   # Another common location
            ]
            
            drive_num = self._get_physical_drive_number(drive_letter)
            success = True
            
            # Search for directory entries containing our MFT record number
            mft_bytes = mft_record.to_bytes(8, 'little')
            
            for index_lba in index_locations:
                try:
                    # Read directory index area
                    data = self.reader.read_volume(drive_letter, index_lba, 10240)  # 20 sectors
                    
                    # Search for MFT record references
                    for i in range(len(data) - 8):
                        if data[i:i+8] == mft_bytes:
                            # Found reference, corrupt this area
                            corrupt_lba = index_lba + (i // 512)
                            corruption_pattern = b'\x00' * 512
                            
                            try:
                                self.disk_io.write_lba_volume(drive_letter, corrupt_lba, corruption_pattern)
                                print(f"    Corrupted directory reference at LBA {corrupt_lba:,}")
                            except:
                                print(f"     Failed to corrupt directory at LBA {corrupt_lba:,}")
                                success = False
                    
                    break
                    
                except Exception as e:
                    print(f"     Failed to process directory at LBA {index_lba:,}: {e}")
                    continue
            
            return success
            
        except Exception as e:
            print(f" Directory reference elimination failed: {e}")
            return False
    
    def eliminate_hard_links(self, drive_letter: str, mft_record: int) -> bool:
        """Eliminate hard link references"""
        try:
            print(f"  Eliminating hard link references for MFT {mft_record} on {drive_letter}:")
            
            # Hard links are additional MFT records that point to the same data
            # We need to find and corrupt any additional records that reference our file
            
            # Search for MFT records that might be hard links
            # Hard links typically have the same file reference number
            
            drive_num = self._get_physical_drive_number(drive_letter)
            
            # Get MFT base location
            mft_base = self.mft_destroyer.find_mft_base_lba(drive_letter)
            if mft_base is None:
                print(f"     Could not locate MFT base for hard link search")
                return False
            
            # Search a range of MFT records for potential hard links
            search_range = 1000  # Search 1000 MFT records
            found_links = 0
            
            for record_offset in range(search_range):
                try:
                    record_lba = mft_base + (record_offset * 2)
                    data = self.reader.read_volume(drive_letter, record_lba, 1024)
                    
                    # Check if this record references our target file
                    # This is simplified - in practice you'd parse the MFT record structure
                    if mft_record.to_bytes(8, 'little') in data:
                        # Found potential hard link, corrupt it
                        corruption_pattern = b'HARD_LINK_CORRUPTED' + b'\x00' * 1004
                        
                        try:
                            self.disk_io.write_lba_volume(drive_letter, record_lba, corruption_pattern)
                            self.disk_io.write_lba_volume(drive_letter, record_lba + 1, corruption_pattern)
                            found_links += 1
                            print(f"    Corrupted hard link at MFT record {record_offset}")
                        except:
                            print(f"     Failed to corrupt hard link at MFT record {record_offset}")
                
                except:
                    continue
            
            print(f"    Found and corrupted {found_links} potential hard links")
            return True
            
        except Exception as e:
            print(f" Hard link elimination failed: {e}")
            return False
    
    def eliminate_security_references(self, drive_letter: str, mft_record: int) -> bool:
        """Eliminate security descriptor references"""
        try:
            print(f"  Eliminating security references for MFT {mft_record} on {drive_letter}:")
            
            # Security descriptors are stored in $Secure file (MFT record 9)
            # We need to corrupt security entries related to our file
            
            # Find $Secure MFT record
            secure_mft_record = 9
            secure_lba = self.mft_destroyer.find_mft_record_lba(drive_letter, secure_mft_record)
            
            if secure_lba is None:
                print(f"     Could not locate $Secure MFT record")
                return False
            
            drive_num = self._get_physical_drive_number(drive_letter)
            
            # Corrupt the $Secure file to eliminate security references
            corruption_patterns = [
                b'\x00' * 1024,
                b'\xFF' * 1024,
                b'SECURITY_CORRUPTED' + b'\x00' * 986
            ]
            
            for i, pattern in enumerate(corruption_patterns):
                try:
                    # Corrupt multiple sectors of $Secure
                    for offset in range(5):  # Corrupt 5 sectors
                        self.disk_io.write_lba_volume(drive_letter, secure_lba + offset, pattern)
                    print(f"    Corrupted $Secure with pattern {i + 1}")
                except Exception as e:
                    print(f"    Failed to corrupt $Secure: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f" Security reference elimination failed: {e}")
            return False
    
    def _get_physical_drive_number(self, drive_letter: str) -> int:
        """Get physical drive number from drive letter"""
        return self.disk_io.get_physical_drive_number(drive_letter)
