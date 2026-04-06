#!/usr/bin/env python3
"""
Drive Filler Module - Fills drives with dummy data for SSD remapping
Implements large sequential writes to force SSD wear-leveling
"""
import os
import sys
import time
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO

class DriveFiller:
    """Handles drive filling operations for SSDs"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        
        print(f"DriveFiller initialized")
    
    def fill_drive_with_data(self, drive_letter: str, drive_size: int) -> bool:
        """Fill entire drive with dummy data to force SSD remapping"""
        try:
            # Create large dummy file to fill drive
            dummy_file = f"{drive_letter}:\\$ssd_secure_fill.tmp"
            
            # Write in large chunks for SSD efficiency
            chunk_size = 64 * 1024 * 1024  # 64MB chunks
            pattern = b'\x00\xFF' * 1024  # Alternating pattern
            
            print(f"      Creating {drive_size / (1024**3):.1f}GB dummy file...")
            
            try:
                with open(dummy_file, 'wb') as f:
                    bytes_written = 0
                    while bytes_written < drive_size:
                        remaining = min(chunk_size, drive_size - bytes_written)
                        f.write(pattern * (remaining // len(pattern) + 1))
                        bytes_written += remaining
                        
                        # Progress indicator
                        if bytes_written % (1024**3) == 0:  # Every GB
                            progress = (bytes_written / drive_size) * 100
                            print(f"      Progress: {progress:.1f}%")
                
                print(f"      Drive fill complete: {bytes_written:,} bytes")
                return True
                
            except Exception as e:
                print(f"      Drive fill failed: {e}")
                return False
                
            finally:
                # Clean up dummy file
                if os.path.exists(dummy_file):
                    try:
                        os.remove(dummy_file)
                        print("      Dummy file removed")
                    except:
                        pass
            
        except Exception as e:
            print(f"      Drive fill error: {e}")
            return False
    
    def overwrite_all_lbas(self, drive_letter: str, pattern: bytes, drive_size: int) -> bool:
        """Overwrite all accessible LBAs on drive"""
        try:
            # Overwrite in large sequential blocks for SSD efficiency
            block_size = 1024 * 1024  # 1MB blocks
            sectors_per_block = block_size // 512
            
            total_sectors = drive_size // 512
            sectors_overwritten = 0
            
            print(f"      Overwriting {total_sectors:,} sectors in {block_size // 1024}KB blocks...")
            
            for sector in range(0, total_sectors, sectors_per_block):
                try:
                    # Write large block
                    for i in range(sectors_per_block):
                        current_lba = sector + i
                        if current_lba >= total_sectors:
                            break
                        self.disk_io.write_lba_volume(drive_letter, current_lba, pattern)
                        sectors_overwritten += 1
                    
                    # Progress
                    if sectors_overwritten % (sectors_per_block * 100) == 0:
                        progress = (sectors_overwritten / total_sectors) * 100
                        print(f"      Progress: {progress:.1f}%")
                    
                except Exception as e:
                    print(f"      Block write failed at LBA {sector}: {e}")
                    return False
                
                print(f"      Complete: {sectors_overwritten:,} sectors overwritten")
                return True
                
        except Exception as e:
            print(f"      Full overwrite failed: {e}")
            return False
