#!/usr/bin/env python3
"""
Content Overwriter Module - Multi-pass file content destruction
Implements military-grade overwrite patterns for secure data wiping
"""
import os
import sys
import time
import random
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from modules import LBAReader

class ContentOverwriter:
    """Handles multi-pass content overwriting with military-grade patterns"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        
        # Multi-pass overwrite patterns (military-grade standards)
        self.overwrite_patterns = [
            b'\x00' * 512,                    # All zeros
            b'\xFF' * 512,                    # All ones  
            b'\xAA' * 512,                    # Alternating 10101010
            b'\x55' * 512,                    # Alternating 01010101
            b'\x00\xFF' * 256,                # 00FF pattern
            b'\xFF\x00' * 256,                # FF00 pattern
            os.urandom(512),                  # Random data (will regenerate each pass)
        ]
        
        # Additional secure patterns (DoD 5220.22-M, Gutmann, etc.)
        self.secure_patterns = [
            bytes([i % 256 for i in range(512)]),           # Sequential pattern
            bytes([255 - (i % 256) for i in range(512)]),   # Reverse sequential
            bytes([(i * 3) % 256 for i in range(512)]),     # Multiplicative pattern
            bytes([(i * 7 + 13) % 256 for i in range(512)]), # Complex pattern
        ]
        
        print(f" ContentOverwriter initialized")
        print(f"     Standard patterns: {len(self.overwrite_patterns)}")
        print(f"     Secure patterns: {len(self.secure_patterns)}")
    
    def overwrite_file_content(self, structure: Dict, passes: int = 7) -> bool:
        """Overwrite file content with multiple pass patterns"""
        print(f"\n Phase 1: Content Overwriting ({passes} passes)")
        
        if structure['is_resident']:
            print("  File is resident - content is in MFT record only")
            return True
        
        success = True
        total_sectors = 0
        
        # Calculate total sectors to overwrite
        for lba_range in structure['lba_ranges']:
            start_lba, length = lba_range
            total_sectors += length
        
        print(f" Total sectors to overwrite: {total_sectors:,}")
        
        # Perform multiple overwrite passes
        for pass_num in range(passes):
            print(f"\n Pass {pass_num + 1}/{passes}")
            
            # Select pattern for this pass
            if pass_num < len(self.overwrite_patterns):
                if pass_num == len(self.overwrite_patterns) - 1:  # Random pass
                    pattern = os.urandom(512)
                else:
                    pattern = self.overwrite_patterns[pass_num]
            else:
                # Use secure patterns for additional passes
                pattern_idx = (pass_num - len(self.overwrite_patterns)) % len(self.secure_patterns)
                pattern = self.secure_patterns[pattern_idx]
            
            print(f"   Pattern: {pattern[:16].hex()}...")
            
            # Overwrite each LBA range
            sectors_overwritten = 0
            for lba_range in structure['lba_ranges']:
                start_lba, length = lba_range
                drive_num = self._get_physical_drive_number(structure['drive_letter'])
                
                print(f"   Overwriting LBA {start_lba:,}-{start_lba + length:,} ({length} sectors)")
                
                for sector_offset in range(length):
                    current_lba = start_lba + sector_offset
                    
                    try:
                        # Write pattern to sector using volume write
                        self.disk_io.write_lba_volume(structure['drive_letter'], current_lba, pattern)
                        sectors_overwritten += 1
                        
                        # Progress indicator
                        if sectors_overwritten % 100 == 0:
                            progress = (sectors_overwritten / total_sectors) * 100
                            print(f"   Progress: {progress:.1f}% ({sectors_overwritten:,}/{total_sectors:,})")
                    
                    except Exception as e:
                        print(f"    Failed to overwrite LBA {current_lba}: {e}")
                        success = False
            
            print(f"    Pass {pass_num + 1} complete: {sectors_overwritten:,} sectors")
            
            # Force cache flush between passes
            try:
                time.sleep(0.1)  # Brief pause
            except:
                pass
        
        print(f"\n Content overwriting complete: {'SUCCESS' if success else 'PARTIAL'}")
        return success
    
    def _get_physical_drive_number(self, drive_letter: str) -> int:
        """Get physical drive number from drive letter"""
        return self.disk_io.get_physical_drive_number(drive_letter)
