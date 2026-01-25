#!/usr/bin/env python3
"""
LBA Content Reader - NTFS Forensics Tool
========================================

Purpose: Reads and analyzes content from specific Logical Block Addresses (LBAs) on physical drives.
This tool can identify MFT records, analyze file signatures, and provide hex dumps of raw disk data.

Features:
- Direct LBA reading from physical drives
- MFT record detection and parsing
- File type identification by signature
- Text encoding detection
- Hex dump visualization

Usage: python 01_lba_reader.py
Requires: Administrator privileges for physical drive access
"""

import ctypes
import os
import struct
from ctypes import wintypes

# Windows API constants
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = -1

class LBAReader:
    """Direct LBA content reader for NTFS forensics"""
    
    def __init__(self, drive_path):
        self.drive_path = drive_path
        self.handle = None
        self.sector_size = 512
    
    def open_drive(self):
        """Open physical drive for reading"""
        self.handle = ctypes.windll.kernel32.CreateFileW(
            self.drive_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if self.handle == INVALID_HANDLE_VALUE:
            raise Exception(f"Cannot open drive {self.drive_path}")
    
    def close_drive(self):
        """Close drive handle"""
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            ctypes.windll.kernel32.CloseHandle(self.handle)
    
    def read_lba_content(self, lba, max_size=None):
        """Read and analyze content from specific LBA"""
        if max_size is None:
            max_size = self.sector_size
        
        # Seek to LBA
        offset = lba * self.sector_size
        high_part = ctypes.c_long(offset >> 32)
        low_part = ctypes.windll.kernel32.SetFilePointer(
            self.handle, offset & 0xFFFFFFFF, ctypes.byref(high_part), 0
        )
        
        # Read data
        buffer = ctypes.create_string_buffer(max_size)
        bytes_read = wintypes.DWORD()
        success = ctypes.windll.kernel32.ReadFile(
            self.handle, buffer, max_size, ctypes.byref(bytes_read), None
        )
        
        if not success:
            raise Exception(f"Failed to read LBA {lba}")
        
        data = buffer.raw[:bytes_read.value]
        
        # Analyze content
        result = {
            'lba': lba,
            'data': data,
            'size': len(data),
            'is_mft_record': self._is_mft_record(data),
            'content_type': 'unknown',
            'analysis': {}
        }
        
        if result['is_mft_record']:
            result['content_type'] = 'mft_record'
            result['analysis'] = self._analyze_mft_record(data)
        else:
            result['content_type'] = 'file_data'
            result['analysis'] = self._analyze_file_data(data)
        
        return result
    
    def _is_mft_record(self, data):
        """Check if data contains MFT record signature"""
        return len(data) >= 4 and data[:4] == b'FILE'
    
    def _analyze_mft_record(self, data):
        """Basic MFT record analysis"""
        if len(data) < 48:
            return {'error': 'MFT record too small'}
        
        try:
            return {
                'signature': data[:4].decode('ascii'),
                'sequence': struct.unpack('<H', data[16:18])[0],
                'link_count': struct.unpack('<H', data[18:20])[0],
                'bytes_in_use': struct.unpack('<L', data[24:28])[0],
                'flags': struct.unpack('<H', data[22:24])[0]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_file_data(self, data):
        """Analyze file data for type and content"""
        analysis = {
            'file_type': 'Unknown',
            'is_text': False,
            'encoding': None,
            'text_preview': None
        }
        
        # File signature detection
        signatures = {
            b'\xFF\xD8\xFF': 'JPEG image',
            b'\x89\x50\x4E\x47': 'PNG image',
            b'\x47\x49\x46\x38': 'GIF image',
            b'\x25\x50\x44\x46': 'PDF document',
            b'\xD0\xCF\x11\xE0': 'Microsoft Office document',
            b'\x52\x61\x72\x21': 'RAR archive'
        }
        
        for sig, file_type in signatures.items():
            if data.startswith(sig):
                analysis['file_type'] = file_type
                break
        
        # Text detection
        try:
            text = data.decode('utf-8')
            analysis['is_text'] = True
            analysis['encoding'] = 'utf-8'
            analysis['text_preview'] = text[:200] + ('...' if len(text) > 200 else '')
        except UnicodeDecodeError:
            # Check for ASCII-like content
            ascii_chars = sum(1 for b in data[:1000] if 32 <= b <= 126 or b in [9, 10, 13])
            if ascii_chars / min(len(data), 1000) > 0.7:
                analysis['is_text'] = True
                analysis['encoding'] = 'ascii-like'
                analysis['text_preview'] = data.decode('ascii', errors='ignore')[:200]
        
        return analysis
    
    def __enter__(self):
        self.open_drive()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_drive()

def get_physical_drive_from_path(file_path):
    """Get physical drive number from file path"""
    drive_letter = os.path.splitdrive(os.path.abspath(file_path))[0]
    drive_char = drive_letter.upper().replace(':', '')
    return 0 if drive_char == 'C' else ord(drive_char) - ord('C')

def read_lba_from_path(file_path, lba, max_size=None):
    """Read LBA content from drive containing the specified file path"""
    try:
        physical_drive_num = get_physical_drive_from_path(file_path)
        drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
        
        with LBAReader(drive_path) as reader:
            return reader.read_lba_content(lba, max_size)
    except Exception as e:
        return {'error': str(e), 'lba': lba, 'file_path': file_path}

if __name__ == "__main__":
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    if not is_admin():
        print("This script requires administrator privileges!")
        exit(1)
    
    # Interactive LBA reading
    while True:
        try:
            lba = int(input("Enter LBA to read (or 0 to exit): "))
            if lba == 0:
                break
            
            result = read_lba_from_path("C:\\", lba, 4096)
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                continue
            
            print(f"\nLBA {lba} Analysis:")
            print(f"Content type: {result['content_type']}")
            print(f"Data size: {len(result['data'])} bytes")
            
            if result['is_mft_record']:
                print("MFT Record detected")
                print(f"Analysis: {result['analysis']}")
            else:
                analysis = result['analysis']
                print(f"File type: {analysis['file_type']}")
                if analysis['is_text']:
                    print(f"Text preview: {analysis['text_preview']}")
            
            # Hex dump
            data = result['data'][:128]
            print("\nHex dump (first 128 bytes):")
            for i in range(0, len(data), 16):
                hex_line = ' '.join(f'{b:02x}' for b in data[i:i+16])
                ascii_line = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[i:i+16])
                print(f"{i:08x}: {hex_line:<48} {ascii_line}")
        
        except KeyboardInterrupt:
            break
        except ValueError:
            print("Invalid LBA number")