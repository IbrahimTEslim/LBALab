#!/usr/bin/env python3
"""
LBA Reader - Direct LBA content reading
Can be run standalone or imported
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI

class LBAReader:
    """Read LBA content from physical drives or volumes"""
    
    def __init__(self):
        self.disk_io = DiskIO()
    
    def read_physical(self, drive_number, lba, size=512):
        """Read from physical drive"""
        return self.disk_io.read_lba_physical(drive_number, lba, size)
    
    def read_volume(self, drive_letter, lba_relative, size=512):
        """Read from volume"""
        return self.disk_io.read_lba_volume(drive_letter, lba_relative, size)
    
    def hex_dump(self, data, offset=0):
        """Format data as hex dump"""
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            hex_part = f"{hex_part:<47}"
            lines.append(f"{offset+i:08x}: {hex_part} | {ascii_part}")
        return '\n'.join(lines)

def main():
    """Standalone CLI"""
    if not WindowsAPI.is_admin():
        print("⚠️  Run as Administrator")
        return 1
    
    if len(sys.argv) < 3:
        print("Usage: lba_reader.py <drive:lba> <size>")
        print("  Physical: lba_reader.py 0:2048 512")
        print("  Volume:   lba_reader.py C:2048 512")
        return 1
    
    reader = LBAReader()
    drive_lba = sys.argv[1]
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 512
    
    try:
        drive, lba = drive_lba.split(':')
        lba = int(lba)
        
        if drive.isdigit():
            # Physical drive
            data = reader.read_physical(int(drive), lba, size)
            print(f"PhysicalDrive{drive} LBA {lba}:")
        else:
            # Volume
            data = reader.read_volume(drive, lba, size)
            print(f"Volume {drive}: LBA {lba}:")
        
        print(reader.hex_dump(data))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
