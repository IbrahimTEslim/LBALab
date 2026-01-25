#!/usr/bin/env python3
"""
NTFS Forensics Toolkit - Main Entry Point
==========================================

This is the main entry point that imports and runs the unified toolkit.
The actual implementation is in tools/ntfs_forensics_toolkit.py
"""

import sys
import os

# Add tools directory to path
tools_dir = os.path.join(os.path.dirname(__file__), 'tools')
sys.path.insert(0, tools_dir)

# Import and run the main toolkit
from ntfs_forensics_toolkit import main

if __name__ == "__main__":
    main()