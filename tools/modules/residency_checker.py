#!/usr/bin/env python3
"""
Residency Checker - Check if file is resident or non-resident
Can be run standalone or imported
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import WindowsAPI
from modules.extent_mapper import ExtentMapper

class ResidencyChecker:
    """Check file residency status"""
    
    def __init__(self):
        self.mapper = ExtentMapper()
    
    def is_file_resident(self, file_path):
        """Check if file is resident (data in MFT) or non-resident (data on disk)"""
        extents = self.mapper.get_file_extents(file_path)
        return extents is None  # No extents = resident

def main():
    """Standalone CLI"""
    if not WindowsAPI.is_admin():
        print("⚠️  Run as Administrator")
        return 1
    
    if len(sys.argv) < 2:
        print("Usage: residency_checker.py <file_path>")
        return 1
    
    checker = ResidencyChecker()
    file_path = sys.argv[1]
    
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return 1
        
        file_size = os.path.getsize(file_path)
        is_resident = checker.is_file_resident(file_path)
        
        print(f"File: {file_path}")
        print(f"Size: {file_size:,} bytes")
        print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
        
        if is_resident:
            print("\nFile data is stored inside the MFT record.")
            print("No additional disk clusters are allocated.")
        else:
            print("\nFile data is stored in clusters on disk.")
            print("Use extent_mapper.py to see the cluster locations.")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
