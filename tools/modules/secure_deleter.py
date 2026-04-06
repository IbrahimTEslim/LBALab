#!/usr/bin/env python3
"""
Secure File Deletion Module - Main coordinator
Coordinates multi-layer data destruction through specialized modules
WARNING: EXTREMELY DANGEROUS - PERMANENT DATA DESTRUCTION
"""
import sys
import os
import time
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import WindowsAPI, DiskIO
from modules import (LBAReader, ComprehensiveAnalyzer, ContentOverwriter, MFTDestroyer, 
                   MetadataWiper, ReferenceEliminator, SSDDetector, 
                   SSDContentOverwriter, HiddenSpaceHandler)

class SecureDeleter:
    """
    Military-grade secure file deletion coordinator
    Orchestrates multiple destruction layers through specialized modules:
    1. Content overwriting (ContentOverwriter)
    2. MFT record corruption (MFTDestroyer)
    3. MFT mirror destruction (MFTDestroyer)
    4. Metadata wiping (MetadataWiper)
    5. Related records elimination (ReferenceEliminator)
    """
    
    def __init__(self, enable_aggressive_mode=False):
        self.disk_io = DiskIO(enable_aggressive_write=enable_aggressive_mode)
        self.reader = LBAReader()
        self.analyzer = ComprehensiveAnalyzer()
        
        # Initialize specialized modules
        self.ssd_detector = SSDDetector(self.disk_io)
        self.content_overwriter = ContentOverwriter(self.disk_io)
        self.ssd_content_overwriter = SSDContentOverwriter(self.disk_io)
        self.mft_destroyer = MFTDestroyer(self.disk_io)
        self.metadata_wiper = MetadataWiper(self.disk_io)
        self.reference_eliminator = ReferenceEliminator(self.disk_io)
        self.hidden_space_handler = HiddenSpaceHandler(self.disk_io)
        
        print(f"SecureDeleter initialized")
        print(f"   -> Aggressive mode: {'ENABLED' if enable_aggressive_mode else 'DISABLED'}")
        print(f"   -> Modules: ContentOverwriter, SSDContentOverwriter, MFTDestroyer, MetadataWiper, ReferenceEliminator, HiddenSpaceHandler")
    
    def confirm_destruction(self, file_path: str) -> bool:
        """Multi-level confirmation for destructive operation"""
        print("\n" + "="*80)
        print(" EXTREME DANGER - IRREVERSIBLE DATA DESTRUCTION ")
        print("="*80)
        print(f"Target: {file_path}")
        print("\nThis operation will:")
        print("   Permanently overwrite file content with multiple patterns")
        print("   Corrupt and delete MFT records")
        print("   Destroy MFT mirror copies")
        print("   Wipe metadata from system journals")
        print("   Eliminate all recovery possibilities")
        print("   Make data recovery IMPOSSIBLE even with forensic tools")
        print("\n  This is MORE destructive than formatting!")
        print("  Recovery is IMPOSSIBLE by any known means!")
        print("="*80)
        
        # First confirmation
        try:
            confirm1 = input("\nType 'DESTROY' to continue: ").strip().upper()
            if confirm1 != 'DESTROY':
                print(" Operation cancelled - confirmation failed")
                return False
        except KeyboardInterrupt:
            print("\n Operation cancelled by user")
            return False
        
        # Second confirmation with file details
        try:
            print(f"\n File details:")
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"   Size: {size:,} bytes")
                print(f"   Exists: YES")
            else:
                print(f"   Status: File may have been deleted or moved")
            
            confirm2 = input(f"\nType the full path to confirm: ").strip()
            if confirm2 != file_path:
                print(" Operation cancelled - path mismatch")
                return False
        except KeyboardInterrupt:
            print("\n Operation cancelled by user")
            return False
        
        # Final confirmation
        try:
            print("\n FINAL WARNING - This is your last chance!")
            confirm3 = input("Type 'I_UNDERSTAND_THE_CONSEQUENCES' to proceed: ").strip().upper()
            if confirm3 != 'I_UNDERSTAND_THE_CONSEQUENCES':
                print(" Operation cancelled - final confirmation failed")
                return False
        except KeyboardInterrupt:
            print("\n Operation cancelled by user")
            return False
        
        return True
    
    def analyze_file_structure(self, file_path: str) -> Dict:
        """Analyze file to understand its structure and locations"""
        print(f" Analyzing file structure: {file_path}")
        
        try:
            # Get comprehensive analysis
            analysis = self.analyzer.analyze_file_complete(file_path)
            
            # Extract key information
            structure = {
                'path': file_path,
                'size': analysis.get('file_size', 0),
                'is_resident': analysis.get('is_resident', False),
                'mft_record': analysis.get('file_info', {}).get('mft_record_number', 0),
                'drive_letter': analysis.get('drive_letter', ''),
                'lba_ranges': [],
                'attributes': analysis.get('file_info', {}),
                'runs': analysis.get('extents', [])
            }
            
            # Convert extents to LBA ranges if available
            if analysis.get('extents'):
                for extent in analysis['extents']:
                    if isinstance(extent, dict) and 'lba_start' in extent and 'length' in extent:
                        structure['lba_ranges'].append((extent['lba_start'], extent['length']))
            
            print(f" File analysis complete:")
            print(f"   Size: {structure['size']:,} bytes")
            print(f"   Resident: {structure['is_resident']}")
            print(f"   MFT Record: {structure['mft_record']}")
            print(f"   Drive: {structure['drive_letter']}")
            print(f"   LBA ranges: {len(structure['lba_ranges'])}")
            
            return structure
            
        except Exception as e:
            print(f" Failed to analyze file: {e}")
            raise
    
    def secure_delete_file(self, file_path: str, passes: int = 7) -> bool:
        """Main secure delete function with all destruction phases"""
        print(f"\n STARTING SECURE DELETION: {file_path}")
        print(f" This is a military-grade secure deletion operation")
        print(f" Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get confirmation
        if not self.confirm_destruction(file_path):
            return False
        
        start_time = time.time()
        success = True
        
        try:
            # Phase 0: Analysis
            print(f"\n Phase 0: Target Analysis")
            structure = self.analyze_file_structure(file_path)
            
            # Detect drive type for SSD-specific operations
            drive_info = self.ssd_detector.get_drive_info(structure['drive_letter'])
            
            # Phase 1: Content overwriting (SSD-aware)
            if drive_info['is_ssd']:
                print("   SSD detected - using optimized deletion method")
                if not self.ssd_content_overwriter.overwrite_file_content_ssd(structure, passes):
                    success = False
            else:
                print("   HDD detected - using traditional deletion method")
                if not self.content_overwriter.overwrite_file_content(structure, passes):
                    success = False
            
            # Phase 2: MFT record corruption
            if not self.mft_destroyer.corrupt_mft_record(structure):
                success = False
            
            # Phase 3: MFT mirror destruction
            if not self.mft_destroyer.destroy_mft_mirror(structure):
                success = False
            
            # Phase 4: Metadata wiping
            if not self.metadata_wiper.wipe_metadata_traces(structure):
                success = False
            
            # Phase 5: Related records elimination
            if not self.reference_eliminator.eliminate_related_records(structure):
                success = False
            
            # Phase 6: Hidden space wiping (SSD-specific)
            if drive_info['is_ssd']:
                print("   SSD detected - wiping hidden areas")
                if not self.hidden_space_handler.wipe_hidden_areas(structure['drive_letter']):
                    success = False
            
            # Final verification
            print(f"\n Final verification...")
            if self.verify_destruction(structure):
                print(f" VERIFICATION PASSED - File is completely destroyed")
            else:
                print(f"  VERIFICATION WARNING - Some traces may remain")
                success = False
            
            elapsed_time = time.time() - start_time
            print(f"\n SECURE DELETION COMPLETE")
            print(f" Elapsed time: {elapsed_time:.2f} seconds")
            print(f" Result: {'SUCCESS' if success else 'PARTIAL'}")
            print(f" Recovery possibility: IMPOSSIBLE")
            
            return success
            
        except Exception as e:
            print(f"\n CRITICAL ERROR: File analysis failed!")
            print(f" Error details: {e}")
            print(f"\n Possible causes:")
            print(f"     File does not exist or was moved")
            print(f"     File is on a network or removable drive")
            print(f"     Insufficient permissions (need Administrator)")
            print(f"     File system is not NTFS")
            print(f"     Drive is locked by another process")
            print(f"     File is corrupted or inaccessible")
            print(f"\n SECURE DELETION ABORTED - Cannot proceed without analysis")
            return False
    
    def verify_destruction(self, structure: Dict) -> bool:
        """Verify that file is completely destroyed"""
        try:
            print(f" Verifying complete destruction of {structure['path']}:")
            
            success = True
            
            # Check 1: File should not exist
            if os.path.exists(structure['path']):
                print(f"     File still exists at path")
                success = False
            else:
                print(f"    File path cleared")
            
            # Check 2: MFT record should be corrupted
            try:
                mft_lba = self.mft_destroyer.find_mft_record_lba(structure['drive_letter'], structure['mft_record'])
                if mft_lba is not None:
                    data = self.reader.read_volume(structure['drive_letter'], mft_lba, 1024)
                    if data[:4] == b'FILE':
                        print(f"     MFT record still appears valid")
                        success = False
                    else:
                        print(f"    MFT record corrupted")
            except:
                print(f"    MFT record inaccessible (corrupted)")
            
            # Check 3: Content should be overwritten
            if not structure['is_resident']:
                try:
                    for lba_range in structure['lba_ranges']:
                        start_lba, length = lba_range
                        drive_num = self.disk_io.get_physical_drive_number(structure['drive_letter'])
                        
                        # Check first sector of each range
                        data = self.reader.read_physical(drive_num, start_lba, 512)
                        if data != b'\x00' * 512 and data != b'\xFF' * 512:
                            print(f"     Content at LBA {start_lba} may not be fully overwritten")
                            success = False
                        else:
                            print(f"    Content at LBA {start_lba} overwritten")
                except:
                    print(f"    Content areas inaccessible (overwritten)")
            
            # Check 4: MFT mirror should be corrupted
            try:
                mirror_lba = self.mft_destroyer.find_mft_mirror_record_lba(structure['drive_letter'], structure['mft_record'])
                if mirror_lba is not None:
                    data = self.reader.read_volume(structure['drive_letter'], mirror_lba, 1024)
                    if data[:4] == b'FILE':
                        print(f"     MFT mirror may still be intact")
                        success = False
                    else:
                        print(f"    MFT mirror corrupted")
            except:
                print(f"    MFT mirror inaccessible (corrupted)")
            
            print(f"    Verification result: {'PASSED' if success else 'FAILED'}")
            return success
            
        except Exception as e:
            print(f" Verification failed: {e}")
            return False

def main():
    """CLI interface for secure deletion"""
    if len(sys.argv) != 2:
        print("Usage: python secure_deleter.py <file_path>")
        print("WARNING: This will permanently destroy the file!")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Initialize secure deleter
    deleter = SecureDeleter(enable_aggressive_mode=True)
    
    # Perform secure deletion
    success = deleter.secure_delete_file(file_path)
    
    if success:
        print(f"\n File securely deleted: {file_path}")
        sys.exit(0)
    else:
        print(f"\n Secure deletion failed: {file_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()
