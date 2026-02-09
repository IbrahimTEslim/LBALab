#!/usr/bin/env python3
"""
MFT Parser - Master File Table record analysis
Can be run standalone or imported
"""
import sys
import os
import struct
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI, NTFSStructures
from core.ntfs_structures import *
import ctypes
from ctypes import wintypes

class MFTParser:
    """Parse and analyze MFT records"""
    
    def __init__(self):
        self.disk_io = DiskIO()
        self.sector_size = 512
    
    def read_mft_record(self, drive_letter, mft_start_lcn, bytes_per_cluster, mft_record_size, mft_index):
        """Read MFT record from volume"""
        handle = self.disk_io.open_volume(drive_letter)
        try:
            offset = (mft_start_lcn * bytes_per_cluster) + (mft_index * mft_record_size)
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offset), None, 0):
                raise OSError("SetFilePointerEx failed")
            
            buf = ctypes.create_string_buffer(mft_record_size)
            read = wintypes.DWORD()
            
            if not ctypes.windll.kernel32.ReadFile(handle, buf, mft_record_size, ctypes.byref(read), None):
                raise OSError("ReadFile failed")
            
            if read.value != mft_record_size:
                raise OSError(f"Only read {read.value} bytes, expected {mft_record_size}")
            
            return buf.raw
        finally:
            WindowsAPI.close_handle(handle)
    
    def parse_mft_attributes(self, mft_data, debug=False):
        """Parse MFT record to find $DATA attributes"""
        if debug:
            print(f"Debug: First 16 bytes: {mft_data[:16].hex()}")
        
        if len(mft_data) < 4 or mft_data[:4] != b'FILE':
            if mft_data[:4] == b'\\x00\\x00\\x00\\x00':
                raise ValueError("MFT record is free/unused")
            elif mft_data[:4] == b'BAAD':
                raise ValueError("MFT record is marked as bad")
            else:
                raise ValueError(f"Invalid MFT signature: {mft_data[:4].hex().upper()}")
        
        if len(mft_data) < 48:
            raise ValueError(f"MFT record too small: {len(mft_data)} bytes")
        
        flags = int.from_bytes(mft_data[22:24], 'little')
        if not (flags & 0x0001):
            raise ValueError("MFT record not marked as in use")
        
        first_attr_offset = int.from_bytes(mft_data[0x14:0x16], "little")
        if first_attr_offset >= len(mft_data):
            raise ValueError("Invalid first attribute offset")
        
        offset = first_attr_offset
        data_attributes = []
        attr_count = 0
        
        while offset < len(mft_data) - 8 and attr_count < 50:
            attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
            
            if attr_type == NTFSStructures.ATTR_END or attr_type == 0:
                break
            
            if offset + 8 > len(mft_data):
                break
            attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
            
            if attr_length < 8 or attr_length > len(mft_data) - offset or attr_length % 4 != 0:
                if debug:
                    print(f"Debug: Invalid attribute length {attr_length} at offset {offset}")
                break
            
            if attr_type == NTFSStructures.ATTR_DATA:
                if offset + 9 <= len(mft_data):
                    non_resident_flag = mft_data[offset + 8]
                    name_length = mft_data[offset + 9] if offset + 9 < len(mft_data) else 0
                    name_offset = int.from_bytes(mft_data[offset + 10:offset + 12], "little") if offset + 12 <= len(mft_data) else 0
                    
                    stream_name = ""
                    if name_length > 0 and name_offset > 0 and offset + name_offset + name_length * 2 <= len(mft_data):
                        name_bytes = mft_data[offset + name_offset:offset + name_offset + name_length * 2]
                        try:
                            stream_name = name_bytes.decode('utf-16le')
                        except:
                            stream_name = f"<invalid_name_{name_length}>"
                    
                    data_attributes.append({
                        'offset': offset,
                        'is_resident': non_resident_flag == 0,
                        'length': attr_length,
                        'stream_name': stream_name,
                        'is_unnamed': name_length == 0
                    })
            
            offset += attr_length
            attr_count += 1
        
        return data_attributes
    
    def parse_mft_header(self, mft_data):
        """Parse MFT record header"""
        if len(mft_data) < 48:
            raise ValueError(f"MFT record too small: {len(mft_data)} bytes")
        
        signature = mft_data[0:4]
        fixup_offset = int.from_bytes(mft_data[4:6], 'little')
        fixup_count = int.from_bytes(mft_data[6:8], 'little')
        lsn = int.from_bytes(mft_data[8:16], 'little')
        sequence_number = int.from_bytes(mft_data[16:18], 'little')
        link_count = int.from_bytes(mft_data[18:20], 'little')
        attrs_offset = int.from_bytes(mft_data[20:22], 'little')
        flags = int.from_bytes(mft_data[22:24], 'little')
        bytes_in_use = int.from_bytes(mft_data[24:28], 'little')
        bytes_allocated = int.from_bytes(mft_data[28:32], 'little')
        base_record = int.from_bytes(mft_data[32:40], 'little')
        next_attr_instance = int.from_bytes(mft_data[40:42], 'little')
        
        flag_descriptions = []
        if flags & 0x0001:
            flag_descriptions.append("IN_USE")
        if flags & 0x0002:
            flag_descriptions.append("DIRECTORY")
        
        return {
            "signature": signature,
            "signature_valid": signature == b'FILE',
            "fixup_offset": fixup_offset,
            "fixup_count": fixup_count,
            "lsn": lsn,
            "sequence_number": sequence_number,
            "link_count": link_count,
            "attrs_offset": attrs_offset,
            "flags": flags,
            "flags_description": " | ".join(flag_descriptions) if flag_descriptions else "NONE",
            "bytes_in_use": bytes_in_use,
            "bytes_allocated": bytes_allocated,
            "base_record": base_record,
            "next_attr_instance": next_attr_instance,
            "is_in_use": bool(flags & 0x0001),
            "is_directory": bool(flags & 0x0002)
        }
    
    def hex_dump(self, data, offset=0, length=None):
        """Format data as hex dump"""
        if length is None:
            length = min(len(data), 256)
        
        lines = []
        for i in range(0, length, 16):
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
    
    if len(sys.argv) < 2:
        print("Usage: mft_parser.py <drive:record> [--hex]")
        print("  Example: mft_parser.py C:5 --hex")
        return 1
    
    parser = MFTParser()
    show_hex = '--hex' in sys.argv
    
    try:
        drive, record = sys.argv[1].split(':')
        record_num = int(record)
        
        # Get volume info
        from modules.file_analyzer import FileAnalyzer
        analyzer = FileAnalyzer()
        vol_info = analyzer.get_volume_info(drive)
        
        print(f"Analyzing MFT record {record_num} from drive {drive}:")
        print("=" * 60)
        
        # Read MFT record
        mft_data = parser.read_mft_record(
            drive, vol_info['mft_start_lcn'], vol_info['bytes_per_cluster'],
            vol_info['mft_record_size'], record_num
        )
        
        print(f"Successfully read {len(mft_data)} bytes")
        
        if show_hex:
            print("\n=== Raw MFT Record Data ===")
            print(parser.hex_dump(mft_data))
            print()
        
        # Parse header
        header = parser.parse_mft_header(mft_data)
        print("\n=== MFT Record Header ===")
        print(f"Signature: {header['signature'].decode('ascii', errors='ignore')} ({'✓ Valid' if header['signature_valid'] else '✗ Invalid'})")
        print(f"Sequence: {header['sequence_number']}")
        print(f"Link Count: {header['link_count']}")
        print(f"Flags: 0x{header['flags']:04x} ({header['flags_description']})")
        print(f"Bytes in Use: {header['bytes_in_use']}")
        
        # Parse attributes
        data_attrs = parser.parse_mft_attributes(mft_data, debug=show_hex)
        if data_attrs:
            print(f"\n$DATA Attributes: {len(data_attrs)}")
            for i, attr in enumerate(data_attrs):
                status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                stream_info = f" ('{attr['stream_name']}')" if attr['stream_name'] else " (unnamed)"
                print(f"  Attribute {i+1}: {status}{stream_info}")
        else:
            print("\nNo $DATA attributes found")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
