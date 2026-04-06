#!/usr/bin/env python3
"""
SSD Content Overwriter Module - Optimized for SSD drives
Implements TRIM + Multiple Overwrites solution for secure SSD deletion
"""
import os
import sys
import time
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO
from modules import LBAReader, SSDDetector, DriveFiller

class SSDContentOverwriter:
    """SSD-optimized content overwriter with TRIM and drive filling"""
    
    def __init__(self, disk_io: DiskIO):
        self.disk_io = disk_io
        self.reader = LBAReader()
        self.drive_filler = DriveFiller(disk_io)
        
        # SSD-optimized overwrite patterns
        self.overwrite_patterns = [
            b'\x00' * 512,                    # All zeros
            b'\xFF' * 512,                    # All ones  
            b'\xAA' * 512,                    # Alternating 10101010
            b'\x55' * 512,                    # Alternating 01010101
            b'\x00\xFF' * 256,                # 00FF pattern
            b'\xFF\x00' * 256,                # FF00 pattern
            os.urandom(512),                  # Random data
        ]
        
        print(f"SSDContentOverwriter initialized")
    
    def overwrite_file_content_ssd(self, structure: Dict, passes: int = 7) -> bool:
        """SSD-optimized content overwriting with TRIM and drive filling"""
        print(f"\nSSD Phase 1: SSD-Optimized Content Overwriting ({passes} passes)")
        
        drive_letter = structure['drive_letter']
        
        # Check if drive is SSD
        drive_info = self.ssd_detector.get_drive_info(drive_letter)
        is_ssd = drive_info['is_ssd']
        trim_supported = drive_info['trim_supported']
        
        print(f"   Drive type: {'SSD' if is_ssd else 'HDD'}")
        print(f"   TRIM support: {'YES' if trim_supported else 'NO'}")
        
        if not is_ssd:
            print("   Using traditional overwrite method...")
            return self._traditional_overwrite(structure, passes)
        
        if not trim_supported:
            print("   WARNING: TRIM not supported - using enhanced overwrite method")
            return self._enhanced_overwrite(structure, passes)
        
        # SSD-specific method
        return self._ssd_optimized_overwrite(structure, passes, trim_supported)
    
    def _ssd_optimized_overwrite(self, structure: Dict, passes: int, trim_supported: bool) -> bool:
        """SSD-optimized overwriting with TRIM and drive filling"""
        drive_letter = structure['drive_letter']
        success = True
        
        # Step 1: Targeted TRIM on file's LBA ranges
        if trim_supported:
            print("   Step 1: Targeted TRIM on file LBAs...")
            if not self.trim_manager.send_targeted_trim(drive_letter, structure['lba_ranges']):
                success = False
        
        # Step 2: Fill drive with dummy data to force remapping
        print("   Step 2: Drive fill to force remapping...")
        drive_size = self._get_drive_size(drive_letter)
        if drive_size > 0:
            if not self.drive_filler.fill_drive_with_data(drive_letter, drive_size):
                print("   WARNING: Drive fill incomplete")
                success = False
        
        # Step 3: Multiple overwrite passes
        print("   Step 3: Multi-pass overwriting...")
        for pass_num in range(passes):
            print(f"   Pass {pass_num + 1}/{passes}")
            
            # Select pattern
            if pass_num < len(self.overwrite_patterns):
                if pass_num == len(self.overwrite_patterns) - 1:
                    pattern = os.urandom(512)
                else:
                    pattern = self.overwrite_patterns[pass_num]
            else:
                # Additional passes with random data
                pattern = os.urandom(512)
            
            print(f"      Pattern: {pattern[:16].hex()}...")
            
            # Overwrite all LBAs (not just file's ranges)
            if not self.drive_filler.overwrite_all_lbas(drive_letter, pattern, drive_size):
                print(f"      Pass {pass_num + 1} failed")
                success = False
        
        # Step 4: Final TRIM
        if trim_supported:
            print("   Step 4: Final TRIM operation...")
            if not self.trim_manager.send_full_trim(drive_letter):
                success = False
        
        return success
    
    def _traditional_overwrite(self, structure: Dict, passes: int) -> bool:
        """Traditional overwrite method for HDDs"""
        print("   Using traditional multi-pass overwrite...")
        
        # Import and use the traditional content overwriter
        from modules.content_overwriter import ContentOverwriter
        traditional_overwriter = ContentOverwriter(self.disk_io)
        return traditional_overwriter.overwrite_file_content(structure, passes)
    
    def _enhanced_overwrite(self, structure: Dict, passes: int) -> bool:
        """Enhanced overwrite for SSDs without TRIM"""
        print("   Using enhanced multi-pass overwrite (no TRIM)...")
        
        # More passes for SSDs without TRIM
        enhanced_passes = passes * 2
        
        # Use traditional overwriter with double passes
        from modules.content_overwriter import ContentOverwriter
        traditional_overwriter = ContentOverwriter(self.disk_io)
        return traditional_overwriter.overwrite_file_content(structure, enhanced_passes)
    
    def _get_drive_size(self, drive_letter: str) -> int:
        """Get total drive size in bytes"""
        try:
            # For now, return a reasonable size estimate
            # In practice, you'd use Windows Storage Manager API
            return 1024 * 1024 * 1024 * 100  # 100GB placeholder
                
        except Exception:
            return 0
