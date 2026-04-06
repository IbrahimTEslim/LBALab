"""
NTFS Toolkit — NTFS forensics, analysis, and education.

Quick start::

    from ntfs_toolkit.analyzers import ComprehensiveAnalyzer
    result = ComprehensiveAnalyzer().analyze(r"C:\\Windows\\notepad.exe")

Modules:
    ntfs_toolkit.core        — Low-level disk I/O and NTFS structures
    ntfs_toolkit.analyzers   — Read-only analysis (LBA, MFT, extents)
    ntfs_toolkit.dangerous   — Write operations (opt-in, destructive)
    ntfs_toolkit.explorer    — Interactive terminal UI with rich panels
    ntfs_toolkit.learn       — Educational lessons with live disk data
"""
__version__ = "3.0.0"
