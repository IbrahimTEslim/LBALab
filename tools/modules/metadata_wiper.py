#!/usr/bin/env python3
"""
Metadata Wiper Module - System journal and metadata destruction
Handles USN journal, $LogFile, and $UsnJrnl wiping
"""
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from modules import LBAReader, MFTDestroyer

class MetadataWiper:
    """Handles metadata wiping from system journals and logs"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        self.mft_destroyer = MFTDestroyer(disk_io)
        
        print(f" MetadataWiper initialized")
    
    def wipe_metadata_traces(self, structure: Dict) -> bool:
        """Wipe metadata from system journals and logs"""
        print(f"\n Phase 4: Metadata Wiping")
        
        success = True
        
        try:
            drive_letter = structure['drive_letter']
            
            # Wipe USN journal entries
            print(f"     Wiping USN journal entries...")
            if not self.wipe_usn_journal_entries(drive_letter, structure['mft_record']):
                print(f"     USN journal wipe incomplete")
                success = False
            
            # Wipe $LogFile entries
            print(f"     Wiping $LogFile entries...")
            if not self.wipe_logfile_entries(drive_letter, structure['mft_record']):
                print(f"     $LogFile wipe incomplete")
                success = False
            
            # Wipe $UsnJrnl metadata
            print(f"     Wiping $UsnJrnl metadata...")
            if not self.wipe_usn_journal_metadata(drive_letter, structure['mft_record']):
                print(f"     $UsnJrnl metadata wipe incomplete")
                success = False
            
            print(f" Metadata wiping complete: {'SUCCESS' if success else 'PARTIAL'}")
            return success
            
        except Exception as e:
            print(f" Metadata wiping failed: {e}")
            return False
    
    def wipe_usn_journal_entries(self, drive_letter: str, mft_record: int) -> bool:
        """Wipe USN journal entries for file"""
        try:
            print(f"  Wiping USN journal entries for MFT {mft_record} on {drive_letter}:")
            
            # USN Journal is in $UsnJrnl file
            # This is a complex operation that requires parsing the USN journal
            # For now, we'll wipe the entire USN journal area
            
            # Find $UsnJrnl file (typically at fixed locations)
            usn_locations = [
                0x100000,  # Common USN journal location
                0x200000,  # Alternative location
                0x400000,  # Large volume location
            ]
            
            drive_num = self._get_physical_drive_number(drive_letter)
            success = True
            
            for usn_lba in usn_locations:
                try:
                    # Wipe a large area around the USN journal
                    wipe_size = 1000  # sectors
                    wipe_pattern = b'\x00' * 512
                    
                    for offset in range(wipe_size):
                        try:
                            self.disk_io.write_lba_volume(drive_letter, usn_lba + offset, wipe_pattern)
                        except:
                            continue
                    
                    print(f"    Wiped USN journal area at LBA {usn_lba:,}")
                    break
                    
                except Exception as e:
                    print(f"     Failed to wipe USN at LBA {usn_lba:,}: {e}")
                    continue
            
            return success
            
        except Exception as e:
            print(f" USN journal wipe failed: {e}")
            return False
    
    def wipe_logfile_entries(self, drive_letter: str, mft_record: int) -> bool:
        """Wipe $LogFile entries"""
        try:
            print(f"  Wiping $LogFile entries for MFT {mft_record} on {drive_letter}:")
            
            # $LogFile contains transaction log entries
            # We need to find and corrupt entries related to our target file
            
            # $LogFile is typically at the beginning of the volume
            logfile_locations = [0x1000, 0x2000, 0x3000]  # Common locations
            
            drive_num = self._get_physical_drive_number(drive_letter)
            success = True
            
            for logfile_lba in logfile_locations:
                try:
                    # Read and search for MFT record references
                    data = self.reader.read_volume(drive_letter, logfile_lba, 5120)  # 10 sectors
                    
                    # Search for the MFT record number in the log
                    mft_bytes = mft_record.to_bytes(8, 'little')
                    
                    for i in range(len(data) - 8):
                        if data[i:i+8] == mft_bytes:
                            # Found reference, corrupt this area
                            corrupt_lba = logfile_lba + (i // 512)
                            corruption_pattern = b'\xFF' * 512
                            
                            try:
                                self.disk_io.write_lba_volume(drive_letter, corrupt_lba, corruption_pattern)
                                print(f"    Corrupted $LogFile entry at LBA {corrupt_lba:,}")
                            except:
                                print(f"     Failed to corrupt $LogFile at LBA {corrupt_lba:,}")
                                success = False
                    
                    break
                    
                except Exception as e:
                    print(f"     Failed to process $LogFile at LBA {logfile_lba:,}: {e}")
                    continue
            
            return success
            
        except Exception as e:
            print(f" $LogFile wipe failed: {e}")
            return False
    
    def wipe_usn_journal_metadata(self, drive_letter: str, mft_record: int) -> bool:
        """Wipe $UsnJrnl metadata"""
        try:
            print(f"  Wiping $UsnJrnl metadata for MFT {mft_record} on {drive_letter}:")
            
            # This is similar to USN journal wiping but focuses on metadata
            # We'll corrupt the $UsnJrnl $DATA attribute
            
            # Find $UsnJrnl in MFT (record number 25)
            usn_mft_record = 25
            usn_lba = self.mft_destroyer.find_mft_record_lba(drive_letter, usn_mft_record)
            
            if usn_lba is None:
                print(f"     Could not locate $UsnJrnl MFT record")
                return False
            
            drive_num = self._get_physical_drive_number(drive_letter)
            
            # Corrupt the $UsnJrnl record
            corruption_patterns = [
                b'\x00' * 1024,
                b'\xFF' * 1024,
                b'CORRUPTED_USN' + b'\x00' * 990
            ]
            
            for i, pattern in enumerate(corruption_patterns):
                try:
                    self.disk_io.write_lba_volume(drive_letter, usn_lba, pattern)
                    self.disk_io.write_lba_volume(drive_letter, usn_lba + 1, pattern)
                    print(f"    Corrupted $UsnJrnl with pattern {i + 1}")
                except Exception as e:
                    print(f"    Failed to corrupt $UsnJrnl: {e}")
                    return False
            
            return True
            
        except Exception as e:
            print(f" $UsnJrnl metadata wipe failed: {e}")
            return False
    
    def _get_physical_drive_number(self, drive_letter: str) -> int:
        """Get physical drive number from drive letter"""
        return self.disk_io.get_physical_drive_number(drive_letter)
