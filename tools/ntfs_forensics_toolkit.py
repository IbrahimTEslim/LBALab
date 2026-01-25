#!/usr/bin/env python3
"""
NTFS Forensics Toolkit - Comprehensive NTFS Analysis Tool
=========================================================

A unified toolkit for NTFS file system forensics and low-level disk analysis.
This open-source tool combines multiple NTFS analysis capabilities into a single,
well-structured application for forensic investigators, system administrators,
and security researchers.

Author: NTFS Forensics Lab
License: MIT License
Version: 2.0.0

Features:
- File to LBA mapping (VCN → LCN → LBA)
- MFT record analysis and extraction
- File residency detection (resident vs non-resident)
- Direct LBA reading and writing
- Partition information analysis
- NTFS volume structure analysis
- File extent mapping and cluster allocation
- Raw disk content analysis
- Named stream detection
- Comprehensive MFT record parsing

Requirements:
- Windows operating system
- Administrator privileges (for low-level disk access)
- Python 3.6+

Usage:
    python ntfs_forensics_toolkit.py [options]
    
    Interactive mode:
        python ntfs_forensics_toolkit.py
    
    Command line examples:
        python ntfs_forensics_toolkit.py --analyze-file "C:\\Windows\\notepad.exe"
        python ntfs_forensics_toolkit.py --read-lba 0:2048
        python ntfs_forensics_toolkit.py --mft-record C:5 --hex
        python ntfs_forensics_toolkit.py --check-residency "C:\\small_file.txt"

Safety Notice:
This tool performs low-level disk operations. Use with caution and ensure
you have proper backups before performing any write operations.
"""

import ctypes
import os
import sys
import struct
import argparse
from ctypes import wintypes
from typing import Dict, List, Tuple, Optional, Union

# Windows API Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_NO_BUFFERING = 0x20000000
INVALID_HANDLE_VALUE = -1

# FSCTL Constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048

# NTFS Attribute Types
ATTR_DATA = 0x80
ATTR_END = 0xFFFFFFFF

class NTFSForensicsError(Exception):
    """Custom exception for NTFS forensics operations"""
    pass

class WindowsStructures:
    """Windows API structure definitions"""
    
    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]
    
    class NTFS_VOLUME_DATA_BUFFER(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", ctypes.c_longlong),
            ("NumberSectors", ctypes.c_longlong),
            ("TotalClusters", ctypes.c_longlong),
            ("FreeClusters", ctypes.c_longlong),
            ("TotalReserved", ctypes.c_longlong),
            ("BytesPerSector", ctypes.c_uint32),
            ("BytesPerCluster", ctypes.c_uint32),
            ("BytesPerFileRecordSegment", ctypes.c_uint32),
            ("ClustersPerFileRecordSegment", ctypes.c_uint32),
            ("MftValidDataLength", ctypes.c_longlong),
            ("MftStartLcn", ctypes.c_longlong),
            ("Mft2StartLcn", ctypes.c_longlong),
            ("MftZoneStart", ctypes.c_longlong),
            ("MftZoneEnd", ctypes.c_longlong)
        ]
    
    class STARTING_VCN_INPUT_BUFFER(ctypes.Structure):
        _fields_ = [("StartingVcn", ctypes.c_longlong)]
    
    class PARTITION_INFORMATION_EX(ctypes.Structure):
        _fields_ = [
            ("PartitionStyle", ctypes.c_int),
            ("StartingOffset", ctypes.c_longlong),
            ("PartitionLength", ctypes.c_longlong),
            ("PartitionNumber", ctypes.c_uint32),
            ("RewritePartition", ctypes.c_byte),
            ("IsServicePartition", ctypes.c_byte),
            ("Padding", ctypes.c_byte * 2),
            ("PartitionInfo", ctypes.c_byte * 112)
        ]

class NTFSForensicsToolkit:
    """Main NTFS forensics toolkit class"""
    
    def __init__(self):
        self.sector_size = 512
        self.structs = WindowsStructures()
    
    def is_admin(self) -> bool:
        """Check if running with Administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def safe_handle_close(self, handle):
        """Safely close a Windows handle"""
        if handle and handle != INVALID_HANDLE_VALUE:
            try:
                ctypes.windll.kernel32.CloseHandle(handle)
            except:
                pass
    
    def open_file(self, path: str):
        """Open file with proper error handling"""
        try:
            abs_path = os.path.abspath(path)
            if not abs_path.startswith("\\\\?\\"):
                abs_path = f"\\\\?\\{abs_path}"
            
            handle = ctypes.windll.kernel32.CreateFileW(
                abs_path, GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSForensicsError(f"Failed to open '{path}': {e}")
    
    def open_volume(self, drive_letter: str):
        """Open volume handle"""
        try:
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None, OPEN_EXISTING, 0, None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSForensicsError(f"Failed to open volume '{drive_letter}:': {e}")
    
    def open_physical_drive(self, drive_number: int, write_access: bool = False):
        """Open physical drive for raw access"""
        try:
            drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
            access = GENERIC_READ
            if write_access:
                access |= GENERIC_WRITE
            
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path, access, FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING,
                FILE_FLAG_NO_BUFFERING if write_access else 0, None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSForensicsError(f"Failed to open PhysicalDrive{drive_number}: {e}")
    
    def get_file_info(self, file_path: str) -> Dict:
        """Get comprehensive file information including MFT record number"""
        file_handle = None
        try:
            file_handle = self.open_file(file_path)
            
            file_info = self.structs.BY_HANDLE_FILE_INFORMATION()
            success = ctypes.windll.kernel32.GetFileInformationByHandle(
                file_handle, ctypes.byref(file_info)
            )
            
            if not success:
                raise ctypes.WinError()
            
            file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
            mft_record_number = file_index & 0xFFFFFFFFFFFF
            sequence_number = (file_index >> 48) & 0xFFFF
            
            return {
                "file_index": file_index,
                "mft_record_number": mft_record_number,
                "sequence_number": sequence_number,
                "volume_serial": file_info.dwVolumeSerialNumber,
                "file_size": (file_info.nFileSizeHigh << 32) | file_info.nFileSizeLow,
                "attributes": file_info.dwFileAttributes,
                "link_count": file_info.nNumberOfLinks
            }
        except Exception as e:
            raise NTFSForensicsError(f"Failed to get file information: {e}")
        finally:
            self.safe_handle_close(file_handle)
    
    def get_ntfs_volume_data(self, vol_handle) -> WindowsStructures.NTFS_VOLUME_DATA_BUFFER:
        """Get NTFS volume information"""
        try:
            vol_info = self.structs.NTFS_VOLUME_DATA_BUFFER()
            returned = wintypes.DWORD()
            res = ctypes.windll.kernel32.DeviceIoControl(
                vol_handle, FSCTL_GET_NTFS_VOLUME_DATA, None, 0,
                ctypes.byref(vol_info), ctypes.sizeof(vol_info),
                ctypes.byref(returned), None
            )
            if not res:
                raise ctypes.WinError()
            return vol_info
        except Exception as e:
            raise NTFSForensicsError(f"Failed to get NTFS volume data: {e}")
    
    def get_sectors_per_cluster(self, drive_letter: str) -> Tuple[int, int]:
        """Get sectors per cluster and bytes per sector"""
        try:
            sectors_per_cluster = wintypes.DWORD()
            bytes_per_sector = wintypes.DWORD()
            free_clusters = wintypes.DWORD()
            total_clusters = wintypes.DWORD()

            res = ctypes.windll.kernel32.GetDiskFreeSpaceW(
                ctypes.c_wchar_p(drive_letter + ":\\\\"),
                ctypes.byref(sectors_per_cluster), ctypes.byref(bytes_per_sector),
                ctypes.byref(free_clusters), ctypes.byref(total_clusters)
            )
            if not res:
                raise ctypes.WinError()

            return sectors_per_cluster.value, bytes_per_sector.value
        except Exception as e:
            raise NTFSForensicsError(f"Failed to get cluster information: {e}")
    
    def read_mft_record(self, drive_letter: str, mft_start_lcn: int, bytes_per_cluster: int, mft_record_size: int, mft_index: int) -> bytes:
        """Read an MFT record from the volume - Enhanced version with 64-bit offset support"""
        handle = None
        try:
            # Validate inputs
            if not isinstance(mft_index, int) or mft_index < 0:
                raise NTFSForensicsError(f"Invalid MFT record number: {mft_index}")
            
            if mft_index > 100000000:  # Reasonable upper bound
                raise NTFSForensicsError(f"MFT record number too large: {mft_index}")
            
            handle = self.open_volume(drive_letter)
            
            # Calculate offset in bytes
            offset = (mft_start_lcn * bytes_per_cluster) + (mft_index * mft_record_size)
            
            # Use SetFilePointerEx for 64-bit offset support (more robust)
            result = ctypes.windll.kernel32.SetFilePointerEx(
                handle,
                ctypes.c_longlong(offset),
                None,
                0  # FILE_BEGIN
            )
            
            if not result:
                raise ctypes.WinError()
            
            # Read MFT record
            buf = ctypes.create_string_buffer(mft_record_size)
            read = wintypes.DWORD()
            
            if not ctypes.windll.kernel32.ReadFile(handle, buf, mft_record_size, ctypes.byref(read), None):
                raise ctypes.WinError()
                
            if read.value != mft_record_size:
                raise NTFSForensicsError(f"Only read {read.value} bytes, expected {mft_record_size}")
                
            return buf.raw
            
        except Exception as e:
            raise NTFSForensicsError(f"Failed to read MFT record {mft_index}: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def parse_mft_attributes(self, mft_data: bytes, debug: bool = False) -> List[Dict]:
        """Parse MFT record to find $DATA attribute and check residency - Enhanced version"""
        try:
            if debug:
                print(f"Debug: First 16 bytes of MFT record: {mft_data[:16].hex()}")
            
            # Verify MFT signature
            if len(mft_data) < 4 or mft_data[:4] != b'FILE':
                if mft_data[:4] == b'\x00\x00\x00\x00':
                    raise NTFSForensicsError("MFT record is free/unused (null signature)")
                elif mft_data[:4] == b'BAAD':
                    raise NTFSForensicsError("MFT record is marked as bad")
                else:
                    raise NTFSForensicsError(f"Invalid MFT signature: {mft_data[:4].hex().upper()} (expected FILE)")
            
            # Parse basic header for validation
            if len(mft_data) < 48:
                raise NTFSForensicsError(f"MFT record too small: {len(mft_data)} bytes (need at least 48)")
            
            flags = int.from_bytes(mft_data[22:24], 'little') if len(mft_data) >= 24 else 0
            if not (flags & 0x0001):  # IN_USE flag
                raise NTFSForensicsError("MFT record is not marked as in use")
            
            # Get first attribute offset
            first_attr_offset = int.from_bytes(mft_data[0x14:0x16], "little")
            
            if first_attr_offset >= len(mft_data):
                raise NTFSForensicsError("Invalid first attribute offset")
            
            # Scan attributes with enhanced validation
            offset = first_attr_offset
            data_attributes = []
            attr_count = 0
            
            while offset < len(mft_data) - 8 and attr_count < 50:  # Safety limit
                # Read attribute type
                attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
                
                # End of attributes
                if attr_type == ATTR_END or attr_type == 0:
                    break
                
                # Read attribute length
                if offset + 8 > len(mft_data):
                    break
                attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
                
                # Enhanced attribute length validation
                if attr_length < 8 or attr_length > len(mft_data) - offset or attr_length % 4 != 0:
                    if debug:
                        print(f"Debug: Invalid attribute length {attr_length} at offset {offset}")
                    break
                
                # Check if this is a $DATA attribute
                if attr_type == ATTR_DATA:
                    # Read non-resident flag (at offset 8 from attribute start)
                    if offset + 9 <= len(mft_data):
                        non_resident_flag = mft_data[offset + 8]
                        
                        # Get attribute name for named streams
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
                
                # Move to next attribute
                offset += attr_length
                attr_count += 1
            
            return data_attributes
            
        except Exception as e:
            raise NTFSForensicsError(f"Failed to parse MFT attributes: {e}")
    
    def get_partition_start_lba(self, drive_letter: str) -> int:
        """Get partition starting LBA"""
        handle = None
        try:
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, 0, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()

            part_info = self.structs.PARTITION_INFORMATION_EX()
            returned = wintypes.DWORD()
            
            res = ctypes.windll.kernel32.DeviceIoControl(
                handle, IOCTL_DISK_GET_PARTITION_INFO_EX, None, 0,
                ctypes.byref(part_info), ctypes.sizeof(part_info),
                ctypes.byref(returned), None
            )
            if not res:
                raise ctypes.WinError()

            return part_info.StartingOffset // self.sector_size
        except Exception as e:
            raise NTFSForensicsError(f"Failed to get partition start LBA: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def get_file_extents(self, file_handle) -> Optional[List[Tuple[int, int, int]]]:
        """Get file extents (VCN → LCN mapping)"""
        try:
            input_buffer = self.structs.STARTING_VCN_INPUT_BUFFER(0)
            out_size = 8192
            output_buffer = ctypes.create_string_buffer(out_size)
            returned = wintypes.DWORD()

            res = ctypes.windll.kernel32.DeviceIoControl(
                file_handle, FSCTL_GET_RETRIEVAL_POINTERS,
                ctypes.byref(input_buffer), ctypes.sizeof(input_buffer),
                output_buffer, out_size, ctypes.byref(returned), None
            )

            if not res:
                err = ctypes.GetLastError()
                if err == 1:  # ERROR_INVALID_FUNCTION - file is resident
                    return None
                raise ctypes.WinError(err)

            if returned.value < 16:
                return None
            
            extent_count = int.from_bytes(output_buffer[0:4], 'little')
            starting_vcn = int.from_bytes(output_buffer[8:16], 'little')
            
            extents = []
            current_vcn = starting_vcn
            
            for i in range(extent_count):
                offset = 16 + i * 16
                if offset + 16 > returned.value:
                    break
                    
                next_vcn = int.from_bytes(output_buffer[offset:offset+8], 'little')
                lcn_raw = output_buffer[offset+8:offset+16]
                
                if lcn_raw == b'\\xff' * 8:
                    lcn = -1  # Sparse
                else:
                    lcn = int.from_bytes(lcn_raw, 'little')
                
                extents.append((current_vcn, next_vcn, lcn))
                current_vcn = next_vcn

            return extents
        except Exception:
            return None
    
    def is_file_resident(self, file_path: str) -> bool:
        """Check if file is resident using cluster allocation method"""
        file_handle = None
        try:
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                raise NTFSForensicsError(f"Invalid file path: {file_path}")
            
            file_handle = self.open_file(file_path)
            extents = self.get_file_extents(file_handle)
            
            return extents is None  # No extents = resident
        except Exception as e:
            raise NTFSForensicsError(f"Error checking file residency: {e}")
        finally:
            self.safe_handle_close(file_handle)
    
    def read_lba(self, drive_number: int, lba: int, size: int = None) -> bytes:
        """Read data from specific LBA"""
        if size is None:
            size = self.sector_size
        
        handle = None
        try:
            handle = self.open_physical_drive(drive_number, write_access=False)
            
            byte_offset = lba * self.sector_size
            low_part = byte_offset & 0xFFFFFFFF
            high_part = (byte_offset >> 32) & 0xFFFFFFFF
            high_part_ptr = ctypes.pointer(wintypes.LONG(high_part))
            
            result = ctypes.windll.kernel32.SetFilePointer(handle, low_part, high_part_ptr, 0)
            if result == 0xFFFFFFFF:
                error = ctypes.windll.kernel32.GetLastError()
                if error != 0:
                    raise Exception(f"Failed to set file pointer. Error: {error}")
            
            aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
            buffer = ctypes.create_string_buffer(aligned_size)
            bytes_read = wintypes.DWORD(0)
            
            success = ctypes.windll.kernel32.ReadFile(handle, buffer, aligned_size, ctypes.byref(bytes_read), None)
            if not success:
                raise Exception(f"Failed to read data. Error: {ctypes.windll.kernel32.GetLastError()}")
            
            return buffer.raw[:size]
        except Exception as e:
            raise NTFSForensicsError(f"Failed to read LBA {lba}: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def analyze_file_complete(self, file_path: str) -> Dict:
        """Complete analysis of a file including LBA mapping - returns structured data"""
        try:
            if not os.path.exists(file_path):
                raise NTFSForensicsError(f"File does not exist: {file_path}")
            
            drive_letter = os.path.splitdrive(file_path)[0].replace(":", "").upper()
            if not drive_letter:
                raise NTFSForensicsError("Could not determine drive letter")
            
            # Get file info
            file_info = self.get_file_info(file_path)
            file_size = os.path.getsize(file_path)
            is_directory = os.path.isdir(file_path)
            
            # Get volume info
            vol_handle = self.open_volume(drive_letter)
            vol_info = self.get_ntfs_volume_data(vol_handle)
            self.safe_handle_close(vol_handle)
            
            partition_start_lba = self.get_partition_start_lba(drive_letter)
            sectors_per_cluster, bytes_per_sector = self.get_sectors_per_cluster(drive_letter)
            
            # Calculate MFT record LBA
            mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
            mft_record_offset_bytes = file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment
            mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
            mft_record_lba_relative = mft_record_absolute_offset // 512
            mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
            
            result = {
                "file_path": file_path,
                "file_size": file_size,
                "is_directory": is_directory,
                "drive_letter": drive_letter,
                "file_info": file_info,
                "volume_info": {
                    "partition_start_lba": partition_start_lba,
                    "bytes_per_sector": bytes_per_sector,
                    "bytes_per_cluster": vol_info.BytesPerCluster,
                    "sectors_per_cluster": sectors_per_cluster,
                    "mft_start_lcn": vol_info.MftStartLcn,
                    "mft_record_size": vol_info.BytesPerFileRecordSegment
                },
                "mft_record_lba": {
                    "relative": mft_record_lba_relative,
                    "absolute": mft_record_lba_absolute,
                    "byte_offset": mft_record_absolute_offset
                },
                "is_resident": None,
                "extents": None,
                "data_attributes": None
            }
            
            # Check residency and get extents for files
            if not is_directory:
                try:
                    # Read and analyze MFT record
                    mft_data = self.read_mft_record(
                        drive_letter, vol_info.MftStartLcn, vol_info.BytesPerCluster,
                        vol_info.BytesPerFileRecordSegment, file_info['mft_record_number']
                    )
                    
                    data_attributes = self.parse_mft_attributes(mft_data)
                    result["data_attributes"] = data_attributes
                    
                    if data_attributes:
                        result["is_resident"] = data_attributes[0]['is_resident']
                        
                        if not result["is_resident"]:
                            file_handle = self.open_file(file_path)
                            extents = self.get_file_extents(file_handle)
                            self.safe_handle_close(file_handle)
                            
                            if extents:
                                extent_details = []
                                for start_vcn, next_vcn, lcn in extents:
                                    cluster_count = next_vcn - start_vcn
                                    if lcn == -1:
                                        extent_details.append({
                                            "start_vcn": start_vcn,
                                            "next_vcn": next_vcn,
                                            "cluster_count": cluster_count,
                                            "lcn": lcn,
                                            "type": "sparse"
                                        })
                                    else:
                                        lba = partition_start_lba + (lcn * sectors_per_cluster)
                                        byte_offset = lba * bytes_per_sector
                                        size_bytes = cluster_count * vol_info.BytesPerCluster
                                        
                                        extent_details.append({
                                            "start_vcn": start_vcn,
                                            "next_vcn": next_vcn,
                                            "cluster_count": cluster_count,
                                            "lcn": lcn,
                                            "lba": lba,
                                            "byte_offset": byte_offset,
                                            "size_bytes": size_bytes,
                                            "type": "allocated"
                                        })
                                
                                result["extents"] = extent_details
                except Exception as e:
                    result["residency_error"] = str(e)
            
            return result
        except Exception as e:
            raise NTFSForensicsError(f"Error analyzing file: {e}")
    
    def hex_dump(self, data: bytes, offset: int = 0, length: int = None, bytes_per_line: int = 16) -> str:
        """Create enhanced hex dump of data with customizable formatting"""
        if length is None:
            length = min(len(data), 256)
        
        lines = []
        for i in range(0, length, bytes_per_line):
            chunk = data[i:i+bytes_per_line]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            # Pad hex part to maintain alignment
            hex_part = f"{hex_part:<{bytes_per_line * 3 - 1}}"
            lines.append(f"{offset+i:08x}: {hex_part} | {ascii_part}")
        
        return '\n'.join(lines)
    
    def analyze_mft_record_header(self, mft_data: bytes) -> Dict:
        """Analyze and parse MFT record header information"""
        if len(mft_data) < 48:
            raise NTFSForensicsError(f"MFT record too small: {len(mft_data)} bytes (need at least 48)")
        
        try:
            # Parse MFT record header
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
            
            # Validate basic sanity checks
            if attrs_offset > len(mft_data):
                raise NTFSForensicsError(f"Invalid attributes offset: {attrs_offset}")
            
            if bytes_in_use > len(mft_data):
                raise NTFSForensicsError(f"Invalid bytes_in_use: {bytes_in_use}")
            
            # Decode flags
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
            
        except Exception as e:
            raise NTFSForensicsError(f"Failed to parse MFT record header: {e}")
    
    def test_common_files(self):
        """Test toolkit with common system files"""
        print("\n" + "=" * 60)
        print("Testing NTFS Forensics Toolkit with common system files:")
        print("=" * 60)
        
        test_files = [
            "C:\\Windows\\win.ini",
            "C:\\Windows\\System32\\drivers\\etc\\hosts",
            "C:\\Windows\\System32\\kernel32.dll"
        ]
        
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"\n{'-' * 50}")
                print(f"Testing: {test_file}")
                print(f"{'-' * 50}")
                try:
                    self.print_file_analysis(test_file)
                except Exception as e:
                    print(f"Error analyzing {test_file}: {e}")
            else:
                print(f"\nTest file not found: {test_file}")
        
        # Test some special MFT records
        print(f"\n{'-' * 50}")
        print("Testing special MFT records:")
        print(f"{'-' * 50}")
        
        special_records = [
            (0, "$MFT"),
            (5, "Root Directory"),
            (6, "$Bitmap")
        ]
        
        for record_num, description in special_records:
            print(f"\n--- {description} (MFT Record {record_num}) ---")
            try:
                self.analyze_mft_record("C", record_num, False)
            except Exception as e:
                print(f"Error accessing MFT record {record_num}: {e}")
    
    def print_file_analysis(self, file_path: str):
        """Print comprehensive file analysis with detailed MFT and extent information"""
        try:
            if not os.path.exists(file_path):
                raise NTFSForensicsError(f"Path does not exist: {file_path}")
            
            drive_letter = os.path.splitdrive(file_path)[0].replace(":", "").upper()
            if not drive_letter:
                raise NTFSForensicsError("Could not determine drive letter")
            
            # Get volume and partition information
            vol_handle = self.open_volume(drive_letter)
            vol_info = self.get_ntfs_volume_data(vol_handle)
            self.safe_handle_close(vol_handle)
            
            partition_start_lba = self.get_partition_start_lba(drive_letter)
            sectors_per_cluster, bytes_per_sector = self.get_sectors_per_cluster(drive_letter)
            
            # Get file information
            file_info = self.get_file_info(file_path)
            is_directory = os.path.isdir(file_path)
            file_size = 0 if is_directory else os.path.getsize(file_path)
            
            # Calculate MFT record LBA
            mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
            mft_record_offset_bytes = file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment
            mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
            mft_record_lba_relative = mft_record_absolute_offset // bytes_per_sector
            mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
            
            # Print comprehensive analysis
            print("=" * 80)
            print(f"NTFS Analysis for: {file_path}")
            print("=" * 80)
            
            # Basic information
            print(f"Type: {'Directory' if is_directory else 'File'}")
            if not is_directory:
                print(f"Size: {file_size:,} bytes")
            print(f"Drive: {drive_letter}:")
            print()
            
            # MFT Record Information
            print("=== MFT Record Information ===")
            print(f"MFT Record Number: {file_info['mft_record_number']:,}")
            print(f"Sequence Number: {file_info['sequence_number']}")
            print(f"MFT Record LBA (relative): {mft_record_lba_relative:,}")
            print(f"MFT Record LBA (absolute): {mft_record_lba_absolute:,}")
            print(f"MFT Record Byte Offset: {mft_record_absolute_offset:,}")
            print()
            
            # Volume Information
            print("=== Volume Information ===")
            print(f"Partition Start LBA: {partition_start_lba:,}")
            print(f"Bytes per Sector: {bytes_per_sector:,}")
            print(f"Bytes per Cluster: {vol_info.BytesPerCluster:,}")
            print(f"Sectors per Cluster: {sectors_per_cluster:,}")
            print(f"MFT Start LCN: {vol_info.MftStartLcn:,}")
            print(f"MFT Record Size: {vol_info.BytesPerFileRecordSegment:,} bytes")
            print()
            
            # For files, check residency and extents
            if not is_directory:
                try:
                    # Read and analyze MFT record
                    mft_data = self.read_mft_record(
                        drive_letter, vol_info.MftStartLcn, vol_info.BytesPerCluster,
                        vol_info.BytesPerFileRecordSegment, file_info['mft_record_number']
                    )
                    
                    data_attributes = self.parse_mft_attributes(mft_data)
                    
                    if not data_attributes:
                        print("=== File Data Status ===")
                        print("No $DATA attribute found")
                    else:
                        first_data_attr = data_attributes[0]
                        is_resident = first_data_attr['is_resident']
                        
                        print("=== File Data Status ===")
                        if is_resident:
                            print("Status: RESIDENT (file data stored inside MFT record)")
                            print("File data is contained within the MFT record itself.")
                            print("No additional LBAs are used for file data storage.")
                        else:
                            print("Status: NON-RESIDENT (file data stored in clusters on disk)")
                            print()
                            
                            # Get file extents for non-resident files
                            file_handle = self.open_file(file_path)
                            extents = self.get_file_extents(file_handle)
                            self.safe_handle_close(file_handle)
                            
                            if extents:
                                print("=== File Data Extents (VCN → LCN → LBA) ===")
                                total_clusters = 0
                                allocated_clusters = 0
                                
                                for i, (start_vcn, next_vcn, lcn) in enumerate(extents):
                                    cluster_count = next_vcn - start_vcn
                                    total_clusters += cluster_count
                                    
                                    if lcn == -1:
                                        print(f"Extent {i+1}: VCN {start_vcn:,}-{next_vcn-1:,} ({cluster_count:,} clusters) → SPARSE (not allocated)")
                                    else:
                                        allocated_clusters += cluster_count
                                        # Calculate LBA
                                        lcn_relative_lba = lcn * sectors_per_cluster
                                        absolute_lba = partition_start_lba + lcn_relative_lba
                                        byte_offset = absolute_lba * bytes_per_sector
                                        size_bytes = cluster_count * vol_info.BytesPerCluster
                                        
                                        print(f"Extent {i+1}: VCN {start_vcn:,}-{next_vcn-1:,} ({cluster_count:,} clusters, {size_bytes:,} bytes)")
                                        print(f"           → LCN {lcn:,} → LBA {absolute_lba:,} → Byte offset {byte_offset:,}")
                                
                                print()
                                print(f"Total clusters: {total_clusters:,}")
                                print(f"Allocated clusters: {allocated_clusters:,}")
                                print(f"Sparse clusters: {total_clusters - allocated_clusters:,}")
                                print(f"Total allocated size: {allocated_clusters * vol_info.BytesPerCluster:,} bytes")
                            else:
                                print("Could not retrieve file extents")
                        
                        # Show additional $DATA attributes if any (named streams)
                        if len(data_attributes) > 1:
                            print()
                            print(f"=== Additional Data Streams ===")
                            print(f"This file has {len(data_attributes)} $DATA attributes (named streams)")
                            for i, attr in enumerate(data_attributes):
                                status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                                stream_info = f" ('{attr['stream_name']}')" if attr['stream_name'] else " (unnamed)"
                                print(f"Stream {i+1}: {status}{stream_info}")
                    
                except Exception as e:
                    print(f"=== File Data Status ===")
                    print(f"Could not determine residency: {e}")
            
            # Show calculation breakdown
            print()
            print("=== MFT Record LBA Calculation ===")
            print(f"1. MFT starts at LCN {vol_info.MftStartLcn:,}")
            print(f"2. MFT byte offset = {vol_info.MftStartLcn:,} × {vol_info.BytesPerCluster:,} = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,}")
            print(f"3. Record {file_info['mft_record_number']:,} offset = {file_info['mft_record_number']:,} × {vol_info.BytesPerFileRecordSegment:,} = {file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,}")
            print(f"4. Total offset = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,} + {file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,} = {mft_record_absolute_offset:,}")
            print(f"5. Relative LBA = {mft_record_absolute_offset:,} ÷ {bytes_per_sector:,} = {mft_record_lba_relative:,}")
            print(f"6. Absolute LBA = {partition_start_lba:,} + {mft_record_lba_relative:,} = {mft_record_lba_absolute:,}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    def analyze_mft_record(self, drive_letter: str, mft_record_number: int, show_hex: bool = False):
        """Analyze a specific MFT record by number"""
        try:
            # Get volume info
            vol_handle = self.open_volume(drive_letter)
            vol_info = self.get_ntfs_volume_data(vol_handle)
            self.safe_handle_close(vol_handle)
            
            partition_start_lba = self.get_partition_start_lba(drive_letter)
            
            # Calculate MFT record LBA
            mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
            mft_record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
            mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
            mft_record_lba_relative = mft_record_absolute_offset // 512
            mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
            
            print(f"Analyzing MFT record {mft_record_number} from drive {drive_letter}:")
            print("=" * 60)
            print(f"MFT Record LBA (relative): {mft_record_lba_relative:,}")
            print(f"MFT Record LBA (absolute): {mft_record_lba_absolute:,}")
            print(f"MFT Record Byte Offset: {mft_record_absolute_offset:,}")
            print()
            
            # Read MFT record
            mft_data = self.read_mft_record(
                drive_letter, vol_info.MftStartLcn, vol_info.BytesPerCluster,
                vol_info.BytesPerFileRecordSegment, mft_record_number
            )
            
            print(f"Successfully read {len(mft_data)} bytes")
            
            # Show hex dump if requested
            if show_hex:
                print("\\n=== Raw MFT Record Data ===")
                print(self.hex_dump(mft_data, 0, min(256, len(mft_data))))
                print()
            
            # Analyze MFT record
            if len(mft_data) >= 4 and mft_data[:4] == b'FILE':
                print("=== MFT Record Analysis ===")
                
                # Parse basic header
                sequence = struct.unpack('<H', mft_data[16:18])[0] if len(mft_data) >= 18 else 0
                link_count = struct.unpack('<H', mft_data[18:20])[0] if len(mft_data) >= 20 else 0
                flags = struct.unpack('<H', mft_data[22:24])[0] if len(mft_data) >= 24 else 0
                bytes_in_use = struct.unpack('<L', mft_data[24:28])[0] if len(mft_data) >= 28 else 0
                
                print(f"Signature: FILE (✓ Valid)")
                print(f"Sequence Number: {sequence}")
                print(f"Link Count: {link_count}")
                print(f"Flags: 0x{flags:04x} ({'IN_USE' if flags & 1 else 'FREE'}{', DIRECTORY' if flags & 2 else ''})")
                print(f"Bytes in Use: {bytes_in_use}")
                
                # Parse attributes
                try:
                    data_attributes = self.parse_mft_attributes(mft_data, debug=show_hex)
                    if data_attributes:
                        print(f"\\n$DATA Attributes: {len(data_attributes)}")
                        for i, attr in enumerate(data_attributes):
                            status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                            stream_info = f" ('{attr['stream_name']}')" if attr['stream_name'] else " (unnamed)"
                            print(f"  Attribute {i+1}: {status}{stream_info}")
                    else:
                        print("\\nNo $DATA attributes found (likely a directory or system file)")
                except Exception as e:
                    print(f"\\nError parsing attributes: {e}")
            else:
                print("=== Invalid MFT Record ===")
                signature = mft_data[:4] if len(mft_data) >= 4 else b''
                print(f"Invalid signature: {signature} (expected FILE)")
                if signature == b'\\x00\\x00\\x00\\x00':
                    print("Record appears to be free/unused")
                elif signature == b'BAAD':
                    print("Record is marked as bad")
            
        except Exception as e:
            print(f"Error: {e}")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(
        description="NTFS Forensics Toolkit - Comprehensive NTFS Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --analyze-file "C:\\Windows\\notepad.exe"
  %(prog)s --read-lba 0:2048
  %(prog)s --check-residency "C:\\small_file.txt"
  %(prog)s --mft-record C:5 --hex
        """
    )
    
    parser.add_argument('--analyze-file', metavar='PATH',
                       help='Analyze file and show LBA mapping')
    parser.add_argument('--read-lba', metavar='DRIVE:LBA',
                       help='Read LBA from physical drive (e.g., 0:2048)')
    parser.add_argument('--check-residency', metavar='PATH',
                       help='Check if file is resident or non-resident')
    parser.add_argument('--mft-record', metavar='DRIVE:RECORD',
                       help='Analyze MFT record (e.g., C:5)')
    parser.add_argument('--test', action='store_true',
                       help='Run tests with common system files')
    parser.add_argument('--hex', action='store_true',
                       help='Show hex dump (use with --mft-record)')
    parser.add_argument('--version', action='version', version='NTFS Forensics Toolkit 2.0.0')
    
    args = parser.parse_args()
    
    toolkit = NTFSForensicsToolkit()
    
    # Check admin privileges
    if not toolkit.is_admin():
        print("⚠️  WARNING: Not running as Administrator.")
        print("   Some operations may fail without Administrator privileges.\\n")
    
    try:
        if args.analyze_file:
            toolkit.print_file_analysis(args.analyze_file)
        
        elif args.read_lba:
            try:
                drive_str, lba_str = args.read_lba.split(':')
                drive_num = int(drive_str)
                lba = int(lba_str)
                
                print(f"Reading LBA {lba} from PhysicalDrive{drive_num}")
                data = toolkit.read_lba(drive_num, lba, 512)
                print(f"Successfully read {len(data)} bytes")
                print("\\nHex dump:")
                print(toolkit.hex_dump(data))
                
                # Check if it's an MFT record
                if len(data) >= 4 and data[:4] == b'FILE':
                    print("\\n*** Detected MFT record signature ***")
            except ValueError:
                print("Invalid format. Use DRIVE:LBA (e.g., 0:2048)")
        
        elif args.check_residency:
            is_resident = toolkit.is_file_resident(args.check_residency)
            file_size = os.path.getsize(args.check_residency)
            print(f"File: {args.check_residency}")
            print(f"Size: {file_size:,} bytes")
            print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
        
        elif args.mft_record:
            try:
                parts = args.mft_record.split(':')
                if len(parts) >= 2:
                    drive = parts[0].upper()
                    record_num = int(parts[1])
                    toolkit.analyze_mft_record(drive, record_num, args.hex)
                else:
                    print("Usage: --mft-record DRIVE:RECORD (e.g., C:5)")
            except ValueError:
                print("Invalid MFT record number")
        
        elif hasattr(args, 'test') and args.test:
            toolkit.test_common_files()
        
        else:
            # Interactive mode
            print("NTFS Forensics Toolkit - Interactive Mode")
            print("=" * 50)
            
            while True:
                print("\\nOptions:")
                print("1. Analyze file")
                print("2. Read LBA")
                print("3. Check file residency")
                print("4. Analyze MFT record")
                print("5. Quit")
                
                choice = input("\\nChoose option (1-5): ").strip()
                
                if choice == "1":
                    path = input("Enter file path: ").strip().strip('"')
                    if path:
                        toolkit.print_file_analysis(path)
                
                elif choice == "2":
                    try:
                        drive_num = int(input("Enter physical drive number: "))
                        lba = int(input("Enter LBA: "))
                        
                        data = toolkit.read_lba(drive_num, lba, 512)
                        print(f"\\nSuccessfully read {len(data)} bytes from LBA {lba}")
                        print("Hex dump:")
                        print(toolkit.hex_dump(data))
                        
                        # Check if it's an MFT record
                        if len(data) >= 4 and data[:4] == b'FILE':
                            print("\\n*** Detected MFT record signature ***")
                    except ValueError:
                        print("Invalid input")
                
                elif choice == "3":
                    path = input("Enter file path: ").strip().strip('"')
                    if path and os.path.exists(path):
                        is_resident = toolkit.is_file_resident(path)
                        file_size = os.path.getsize(path)
                        print(f"\\nFile: {path}")
                        print(f"Size: {file_size:,} bytes")
                        print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
                
                elif choice == "4":
                    try:
                        drive = input("Enter drive letter (default C): ").strip().upper() or "C"
                        record_num = int(input("Enter MFT record number: "))
                        show_hex = input("Show hex dump? (y/n, default n): ").strip().lower().startswith('y')
                        print()
                        toolkit.analyze_mft_record(drive, record_num, show_hex)
                    except ValueError:
                        print("Invalid MFT record number")
                
                elif choice == "5":
                    break
                else:
                    print("Invalid option")
    
    except KeyboardInterrupt:
        print("\\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()