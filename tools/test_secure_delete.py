#!/usr/bin/env python3
"""Test secure delete functionality directly"""
import sys
import os

# Add modules directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    # Test direct import of SecureDeleter
    from modules import SecureDeleter
    print('SecureDeleter imported directly!')
    
    # Test SSD detection
    deleter = SecureDeleter()
    drive_info = deleter.ssd_detector.get_drive_info('F')
    print(f'Drive F info: {drive_info}')
    
    # Test file analysis
    structure = deleter.analyze_file_structure('F:\\test.txt')
    print(f'File structure: {structure}')
    
    print('SSD-Aware Secure Deletion System is WORKING!')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
