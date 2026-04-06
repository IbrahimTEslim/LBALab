#!/usr/bin/env python3
"""Test script to bypass import cache issues"""
import sys
import os

# Add modules directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Test direct imports
try:
    from modules import SSDDetector, DriveFiller, TRIMManager, SSDContentOverwriter
    print('All SSD modules imported successfully!')
    
    # Test secure deleter
    from modules import SecureDeleter
    print('SecureDeleter imported successfully!')
    
    print('Import cache issue resolved!')
    
except Exception as e:
    print(f'Import error: {e}')
    import traceback
    traceback.print_exc()
