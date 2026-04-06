#!/usr/bin/env python3
"""
LBA Writer - Write data to specific LBA
Can be run standalone or imported
 DANGEROUS - Writes directly to disk!
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI
from modules import LBAReader

class LBAWriter:
    """Write data to LBA on physical drives or volumes"""
    
    def __init__(self, enable_aggressive_write=False):
        self.disk_io = DiskIO(enable_aggressive_write=enable_aggressive_write)
        self.reader = LBAReader()
    
    def write_physical(self, drive_number, lba, data, confirm=True):
        """Write to physical drive with safety checks"""
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        
        if confirm:
            print(f"  WARNING: Writing to PhysicalDrive{drive_number} LBA {lba}")
            print(f"   This will OVERWRITE {len(data)} bytes on the disk!")
            print(f"   Data: {data[:64]}")
            
            # Show what will be overwritten
            try:
                current = self.reader.read_physical(drive_number, lba, 512)
                print(f"\n   Current content: {current[:64].hex()}")
            except:
                pass
            
            response = input("\n   Type 'YES' to confirm: ")
            if response != 'YES':
                print("   Cancelled.")
                return 0
        
        bytes_written = self.disk_io.write_lba_physical(drive_number, lba, data)
        print(f" Wrote {bytes_written} bytes to PhysicalDrive{drive_number} LBA {lba}")
        return bytes_written
    
    def write_volume(self, drive_letter, lba_relative, data, confirm=True):
        """Write to volume with safety checks"""
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        
        if confirm:
            print(f"  WARNING: Writing to Volume {drive_letter}: LBA {lba_relative}")
            print(f"   This will OVERWRITE {len(data)} bytes!")
            print(f"   Data: {data[:64]}")
            print(f"\n   IMPORTANT: Close all files/programs using {drive_letter}: drive!")
            
            try:
                current = self.reader.read_volume(drive_letter, lba_relative, 512)
                print(f"\n   Current content: {current[:64].hex()}")
            except:
                pass
            
            input("\n   Press Enter when ready...")
            response = input("   Type 'YES' to confirm: ")
            if response != 'YES':
                print("   Cancelled.")
                return 0
        
        bytes_written = self.disk_io.write_lba_volume(drive_letter, lba_relative, data)
        print(f" Wrote {bytes_written} bytes to Volume {drive_letter}: LBA {lba_relative}")
        return bytes_written

def main():
    """Standalone CLI"""
    if not WindowsAPI.is_admin():
        print("  Must run as Administrator")
        return 1
    
    if len(sys.argv) < 3:
        print("Usage: lba_writer.py <drive:lba> <data>")
        print("  Physical: lba_writer.py 0:2048 'Hello World'")
        print("  Volume:   lba_writer.py D:2048 'Test Data'")
        return 1
    
    writer = LBAWriter()
    drive_lba = sys.argv[1]
    data = sys.argv[2]
    
    try:
        drive, lba = drive_lba.split(':')
        lba = int(lba)
        
        if drive.isdigit():
            writer.write_physical(int(drive), lba, data)
        else:
            writer.write_volume(drive, lba, data)
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
