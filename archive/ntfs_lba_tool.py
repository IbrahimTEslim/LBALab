#!/usr/bin/env python3
"""
NTFS LBA Analysis and Manipulation Tool
Comprehensive tool for NTFS file system analysis, LBA operations, and MFT record handling.

Features:
- File to LBA mapping (VCN → LCN → LBA)
- MFT record analysis and fetching
- File residency detection
- Direct LBA reading and writing
- Partition information retrieval
- Raw disk content analysis

Requires Administrator privileges for low-level disk operations.
"""

import ctypes
import os
import sys
import struct
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
INVALID_HANDLE_VALUE = -1
FILE_BEGIN = 0

# NTFS Attribute types
ATTR_STANDARD_INFORMATION = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME = 0x30
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_INDEX_ALLOCATION = 0xA0
ATTR_END = 0xFFFFFFFF

# Error codes
ERROR_INVALID_FUNCTION = 1
ERROR_HANDLE_EOF = 38

# Structures
class STARTING_VCN_INPUT_BUFFER(ctypes.Structure):
    _fields_ = [("StartingVcn", ctypes.c_longlong)]

class MBR_PARTITION_INFO(ctypes.Structure):
    _fields_ = [
        ("PartitionType", ctypes.c_byte),
        ("BootIndicator", ctypes.c_byte),
        ("RecognizedPartition", ctypes.c_byte),
        ("HiddenSectors", ctypes.c_uint32)
    ]

class GPT_PARTITION_INFO(ctypes.Structure):
    _fields_ = [
        ("PartitionType", ctypes.c_byte * 16),
        ("PartitionId", ctypes.c_byte * 16),
        ("Attributes", ctypes.c_longlong),
        ("Name", ctypes.c_wchar * 36)
    ]

class PARTITION_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("Mbr", MBR_PARTITION_INFO),
        ("Gpt", GPT_PARTITION_INFO)
    ]

class PARTITION_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("PartitionStyle", ctypes.c_int),
        ("StartingOffset", ctypes.c_longlong),
        ("PartitionLength", ctypes.c_longlong),
        ("PartitionNumber", ctypes.c_uint32),
        ("RewritePartition", ctypes.c_byte),
        ("IsServicePartition", ctypes.c_byte),
        ("Padding", ctypes.c_byte * 2),
        ("PartitionInfo", PARTITION_INFO_UNION)
    ]

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

class NTFSLBAError(Exception):
    """Custom exception for NTFS LBA operations"""
    pass

class NTFSLBATool:
    """Comprehensive NTFS LBA analysis and manipulation tool"""
    
    def __init__(self):
        self.sector_size = 512
        
    def is_admin(self):
        """Check if running with Administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def safe_handle_close(self, handle):
        """Safely close a handle if it's valid"""
        if handle and handle != INVALID_HANDLE_VALUE:
            try:
                ctypes.windll.kernel32.CloseHandle(handle)
            except:
                pass
    
    def open_file(self, path):
        """Open a file handle with proper error handling"""
        try:
            abs_path = os.path.abspath(path)
            if not abs_path.startswith("\\\\?\\"):
                abs_path = r"\\?\{}".format(abs_path)
            
            handle = ctypes.windll.kernel32.CreateFileW(
                abs_path,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSLBAError(f"Failed to open '{path}': {e}")
    
    def open_volume(self, drive_letter):
        """Open a volume handle"""
        try:
            volume_path = r"\\.\{}:".format(drive_letter.upper())
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSLBAError(f"Failed to open volume '{drive_letter}:': {e}")
    
    def open_physical_drive(self, drive_number, write_access=False):
        """Open physical drive for raw access"""
        try:
            drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
            access = GENERIC_READ
            if write_access:
                access |= GENERIC_WRITE
            
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path,
                access,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                FILE_FLAG_NO_BUFFERING if write_access else 0,
                None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()
            return handle
        except Exception as e:
            raise NTFSLBAError(f"Failed to open PhysicalDrive{drive_number}: {e}")
    
    def get_ntfs_volume_data(self, vol_handle):
        """Get NTFS volume information"""
        try:
            vol_info = NTFS_VOLUME_DATA_BUFFER()
            returned = wintypes.DWORD()
            res = ctypes.windll.kernel32.DeviceIoControl(
                vol_handle,
                FSCTL_GET_NTFS_VOLUME_DATA,
                None,
                0,
                ctypes.byref(vol_info),
                ctypes.sizeof(vol_info),
                ctypes.byref(returned),
                None
            )
            if not res:
                raise ctypes.WinError()
            return vol_info
        except Exception as e:
            raise NTFSLBAError(f"Failed to get NTFS volume data: {e}")
    
    def get_partition_start_lba(self, drive_letter):
        """Get partition starting LBA"""
        handle = None
        try:
            volume_path = r"\\.\{}:".format(drive_letter.upper())
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path,
                0,
                FILE_SHARE_READ,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            if handle == INVALID_HANDLE_VALUE:
                raise ctypes.WinError()

            part_info = PARTITION_INFORMATION_EX()
            returned = wintypes.DWORD()
            
            res = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                IOCTL_DISK_GET_PARTITION_INFO_EX,
                None,
                0,
                ctypes.byref(part_info),
                ctypes.sizeof(part_info),
                ctypes.byref(returned),
                None
            )
            if not res:
                raise ctypes.WinError()

            starting_lba = part_info.StartingOffset // self.sector_size
            return starting_lba
        except Exception as e:
            raise NTFSLBAError(f"Failed to get partition start LBA: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def get_sectors_per_cluster(self, drive_letter):
        """Get sectors per cluster and bytes per sector"""
        try:
            sectors_per_cluster = wintypes.DWORD()
            bytes_per_sector = wintypes.DWORD()
            free_clusters = wintypes.DWORD()
            total_clusters = wintypes.DWORD()

            root_path = drive_letter.upper() + ":\\"
            res = ctypes.windll.kernel32.GetDiskFreeSpaceW(
                ctypes.c_wchar_p(root_path),
                ctypes.byref(sectors_per_cluster),
                ctypes.byref(bytes_per_sector),
                ctypes.byref(free_clusters),
                ctypes.byref(total_clusters)
            )
            if not res:
                raise ctypes.WinError()

            return sectors_per_cluster.value, bytes_per_sector.value
        except Exception as e:
            raise NTFSLBAError(f"Failed to get cluster information: {e}")
    
    def get_file_extents(self, file_handle):
        """Get file extents (VCN → LCN mapping)"""
        try:
            input_buffer = STARTING_VCN_INPUT_BUFFER(0)
            out_size = 8192
            output_buffer = ctypes.create_string_buffer(out_size)
            returned = wintypes.DWORD()

            res = ctypes.windll.kernel32.DeviceIoControl(
                file_handle,
                FSCTL_GET_RETRIEVAL_POINTERS,
                ctypes.byref(input_buffer),
                ctypes.sizeof(input_buffer),
                output_buffer,
                out_size,
                ctypes.byref(returned),
                None
            )

            if not res:
                err = ctypes.GetLastError()
                if err == ERROR_INVALID_FUNCTION:
                    return None  # File is resident
                raise ctypes.WinError(err)

            if returned.value < 16:
                return None
            
            extent_count = int.from_bytes(output_buffer[0:4], 'little')
            starting_vcn = int.from_bytes(output_buffer[8:16], 'little')
            
            if extent_count > 10000:
                raise ValueError(f"ExtentCount {extent_count} seems too large")
            
            expected_size = 16 + extent_count * 16
            if returned.value < expected_size:
                raise ValueError(f"Buffer size {returned.value} too small for {extent_count} extents")
            
            extents = []
            current_vcn = starting_vcn
            
            for i in range(extent_count):
                offset = 16 + i * 16
                next_vcn = int.from_bytes(output_buffer[offset:offset+8], 'little')
                lcn_raw = output_buffer[offset+8:offset+16]
                
                if lcn_raw == b'\xff' * 8:
                    lcn = -1  # Sparse
                else:
                    lcn = int.from_bytes(lcn_raw, 'little')
                
                extents.append((current_vcn, next_vcn, lcn))
                current_vcn = next_vcn

            return extents
        except Exception:
            return None
    
    def get_file_info(self, file_path):
        """Get file information including MFT record number"""
        file_handle = None
        try:
            file_handle = self.open_file(file_path)
            
            file_info = BY_HANDLE_FILE_INFORMATION()
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
            raise NTFSLBAError(f"Failed to get file information: {e}")
        finally:
            self.safe_handle_close(file_handle)
    
    def is_file_resident(self, file_path):
        """Check if file is resident using cluster allocation method"""
        file_handle = None
        try:
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                raise NTFSLBAError(f"Invalid file path: {file_path}")
            
            file_handle = self.open_file(file_path)
            extents = self.get_file_extents(file_handle)
            
            return extents is None  # No extents = resident
        except Exception as e:
            raise NTFSLBAError(f"Error checking file residency: {e}")
        finally:
            self.safe_handle_close(file_handle)
    
    def fetch_mft_record(self, drive_letter, mft_record_number):
        """Fetch raw MFT record data"""
        vol_handle = None
        try:
            vol_handle = self.open_volume(drive_letter)
            vol_info = self.get_ntfs_volume_data(vol_handle)
            
            mft_start_byte_offset = vol_info.MftStartLcn * vol_info.BytesPerCluster
            record_byte_offset = mft_record_number * vol_info.BytesPerFileRecordSegment
            absolute_offset = mft_start_byte_offset + record_byte_offset
            
            # Fixed: Use SetFilePointerEx for proper 64-bit offset handling
            result = ctypes.windll.kernel32.SetFilePointerEx(
                vol_handle,
                ctypes.c_longlong(absolute_offset),
                None,
                0
            )
            
            if not result:
                error_code = ctypes.windll.kernel32.GetLastError()
                raise ctypes.WinError(error_code)
            
            record_size = vol_info.BytesPerFileRecordSegment
            buffer = ctypes.create_string_buffer(record_size)
            bytes_read = wintypes.DWORD()
            
            success = ctypes.windll.kernel32.ReadFile(
                vol_handle, buffer, record_size, ctypes.byref(bytes_read), None
            )
            
            if not success:
                raise ctypes.WinError()
            
            if bytes_read.value != record_size:
                raise NTFSLBAError(f"Read {bytes_read.value} bytes, expected {record_size}")
            
            return buffer.raw
        except Exception as e:
            raise NTFSLBAError(f"Failed to fetch MFT record {mft_record_number}: {e}")
        finally:
            self.safe_handle_close(vol_handle)
    
    def analyze_mft_record(self, mft_data):
        """Analyze MFT record header and attributes"""
        if len(mft_data) < 48:
            raise NTFSLBAError(f"MFT record too small: {len(mft_data)} bytes")
        
        try:
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
            
            header_info = {
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
            
            # Parse attributes
            data_attributes = []
            if header_info['signature_valid'] and header_info['is_in_use']:
                offset = attrs_offset
                attr_count = 0
                
                while offset < len(mft_data) - 8 and attr_count < 50:
                    if offset + 4 > len(mft_data):
                        break
                    
                    attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
                    
                    if attr_type == ATTR_END or attr_type == 0:
                        break
                    
                    if offset + 8 > len(mft_data):
                        break
                    
                    attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
                    
                    if attr_length < 8 or attr_length > len(mft_data) - offset or attr_length % 4 != 0:
                        break
                    
                    if attr_type == ATTR_DATA:
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
            
            header_info['data_attributes'] = data_attributes
            return header_info
            
        except Exception as e:
            raise NTFSLBAError(f"Failed to analyze MFT record: {e}")
    
    def read_lba(self, drive_number, lba, size=None):
        """Read data from specific LBA"""
        if size is None:
            size = self.sector_size
        
        handle = None
        try:
            handle = self.open_physical_drive(drive_number, write_access=False)
            
            # Calculate byte offset
            byte_offset = lba * self.sector_size
            
            # Set file pointer
            low_part = byte_offset & 0xFFFFFFFF
            high_part = (byte_offset >> 32) & 0xFFFFFFFF
            high_part_ptr = ctypes.pointer(wintypes.LONG(high_part))
            
            result = ctypes.windll.kernel32.SetFilePointer(handle, low_part, high_part_ptr, 0)
            if result == 0xFFFFFFFF:
                error = ctypes.windll.kernel32.GetLastError()
                if error != 0:
                    raise Exception(f"Failed to set file pointer. Error: {error}")
            
            # Read data
            aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
            buffer = ctypes.create_string_buffer(aligned_size)
            bytes_read = wintypes.DWORD(0)
            
            success = ctypes.windll.kernel32.ReadFile(handle, buffer, aligned_size, ctypes.byref(bytes_read), None)
            if not success:
                raise Exception(f"Failed to read data. Error: {ctypes.windll.kernel32.GetLastError()}")
            
            return buffer.raw[:size]
        except Exception as e:
            raise NTFSLBAError(f"Failed to read LBA {lba}: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def write_lba(self, drive_number, lba, data):
        """Write data to specific LBA"""
        if not self.is_admin():
            raise NTFSLBAError("Administrator privileges required for write operations")
        
        handle = None
        try:
            handle = self.open_physical_drive(drive_number, write_access=True)
            
            # Ensure data is bytes and properly sized
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if len(data) < self.sector_size:
                data = data + b'\x00' * (self.sector_size - len(data))
            elif len(data) > self.sector_size:
                data = data[:self.sector_size]
            
            # Calculate byte offset
            byte_offset = lba * self.sector_size
            
            # Set file pointer
            low_part = byte_offset & 0xFFFFFFFF
            high_part = (byte_offset >> 32) & 0xFFFFFFFF
            high_part_ptr = ctypes.pointer(wintypes.LONG(high_part))
            
            result = ctypes.windll.kernel32.SetFilePointer(handle, low_part, high_part_ptr, 0)
            if result == 0xFFFFFFFF:
                error = ctypes.windll.kernel32.GetLastError()
                if error != 0:
                    raise Exception(f"Failed to set file pointer. Error: {error}")
            
            # Write data
            buffer = ctypes.create_string_buffer(data)
            bytes_written = wintypes.DWORD()
            
            success = ctypes.windll.kernel32.WriteFile(handle, buffer, len(data), ctypes.byref(bytes_written), None)
            if not success:
                raise Exception(f"Write failed. Error: {ctypes.windll.kernel32.GetLastError()}")
            
            # Flush buffers
            ctypes.windll.kernel32.FlushFileBuffers(handle)
            
            return bytes_written.value
        except Exception as e:
            raise NTFSLBAError(f"Failed to write LBA {lba}: {e}")
        finally:
            self.safe_handle_close(handle)
    
    def get_physical_drive_number(self, drive_letter):
        """Simple mapping of drive letter to physical drive number"""
        drive_char = drive_letter.upper()
        if drive_char == 'C':
            return 0
        else:
            return ord(drive_char) - ord('C')
    
    def analyze_file_complete(self, file_path):
        """Complete analysis of a file including LBA mapping"""
        try:
            if not os.path.exists(file_path):
                raise NTFSLBAError(f"File does not exist: {file_path}")
            
            drive_letter = os.path.splitdrive(file_path)[0].replace(":", "").upper()
            if not drive_letter:
                raise NTFSLBAError("Could not determine drive letter")
            
            # Get basic file info
            file_info = self.get_file_info(file_path)
            file_size = os.path.getsize(file_path)
            is_directory = os.path.isdir(file_path)
            
            # Get volume and partition info
            vol_handle = self.open_volume(drive_letter)
            vol_info = self.get_ntfs_volume_data(vol_handle)
            self.safe_handle_close(vol_handle)
            
            partition_start_lba = self.get_partition_start_lba(drive_letter)
            sectors_per_cluster, bytes_per_sector = self.get_sectors_per_cluster(drive_letter)
            
            # Calculate MFT record LBA - FIXED to always use 512 bytes per sector
            mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
            mft_record_offset_bytes = file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment
            mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
            mft_record_lba_relative = mft_record_absolute_offset // 512  # Always use 512 for LBA
            mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
            
            result = {
                "file_path": file_path,
                "file_size": file_size,
                "is_directory": is_directory,
                "drive_letter": drive_letter,
                "file_info": file_info,
                "volume_info": {
                    "partition_start_lba": partition_start_lba,
                    "sectors_per_cluster": sectors_per_cluster,
                    "bytes_per_sector": bytes_per_sector,
                    "bytes_per_cluster": vol_info.BytesPerCluster,
                    "mft_start_lcn": vol_info.MftStartLcn,
                    "mft_record_size": vol_info.BytesPerFileRecordSegment
                },
                "mft_record_lba": {
                    "relative": mft_record_lba_relative,
                    "absolute": mft_record_lba_absolute,
                    "byte_offset": mft_record_absolute_offset
                },
                "is_resident": None,
                "extents": None
            }
            
            # Check residency and get extents for files
            if not is_directory:
                try:
                    result["is_resident"] = self.is_file_resident(file_path)
                    
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
            raise NTFSLBAError(f"Error analyzing file: {e}")
    
    def hex_dump(self, data, offset=0, length=None):
        """Create hex dump of data"""
        if length is None:
            length = min(len(data), 256)
        
        lines = []
        for i in range(0, length, 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{offset+i:08x}: {hex_part:<48} {ascii_part}")
        
        return '\n'.join(lines)
    
    def print_file_analysis(self, file_path):
        """Print comprehensive file analysis"""
        try:
            analysis = self.analyze_file_complete(file_path)
            
            print("=" * 80)
            print(f"NTFS File Analysis: {analysis['file_path']}")
            print("=" * 80)
            
            # Basic info
            print(f"Type: {'Directory' if analysis['is_directory'] else 'File'}")
            if not analysis['is_directory']:
                print(f"Size: {analysis['file_size']:,} bytes")
            print(f"Drive: {analysis['drive_letter']}:")
            print()
            
            # MFT Record info
            print("=== MFT Record Information ===")
            print(f"MFT Record Number: {analysis['file_info']['mft_record_number']:,}")
            print(f"Sequence Number: {analysis['file_info']['sequence_number']}")
            print(f"MFT Record LBA (relative): {analysis['mft_record_lba']['relative']:,}")
            print(f"MFT Record LBA (absolute): {analysis['mft_record_lba']['absolute']:,}")
            print(f"MFT Record Byte Offset: {analysis['mft_record_lba']['byte_offset']:,}")
            print()
            
            # Volume info
            vol_info = analysis['volume_info']
            print("=== Volume Information ===")
            print(f"Partition Start LBA: {vol_info['partition_start_lba']:,}")
            print(f"Bytes per Sector: {vol_info['bytes_per_sector']:,}")
            print(f"Bytes per Cluster: {vol_info['bytes_per_cluster']:,}")
            print(f"Sectors per Cluster: {vol_info['sectors_per_cluster']:,}")
            print(f"MFT Start LCN: {vol_info['mft_start_lcn']:,}")
            print(f"MFT Record Size: {vol_info['mft_record_size']:,} bytes")
            print()
            
            # File data analysis
            if not analysis['is_directory']:
                print("=== File Data Analysis ===")
                if analysis['is_resident'] is not None:
                    if analysis['is_resident']:
                        print("Status: RESIDENT (data stored in MFT record)")
                    else:
                        print("Status: NON-RESIDENT (data stored in disk clusters)")
                        
                        if analysis['extents']:
                            print(f"\nExtents: {len(analysis['extents'])} extent(s)")
                            print("\nVCN → LCN → LBA Mapping:")
                            
                            total_clusters = 0
                            allocated_clusters = 0
                            
                            for i, extent in enumerate(analysis['extents']):
                                total_clusters += extent['cluster_count']
                                
                                if extent['type'] == 'sparse':
                                    print(f"  Extent {i+1}: VCN {extent['start_vcn']:,}-{extent['next_vcn']-1:,} "
                                          f"({extent['cluster_count']:,} clusters) → SPARSE")
                                else:
                                    allocated_clusters += extent['cluster_count']
                                    print(f"  Extent {i+1}: VCN {extent['start_vcn']:,}-{extent['next_vcn']-1:,} "
                                          f"({extent['cluster_count']:,} clusters)")
                                    print(f"             → LCN {extent['lcn']:,} → LBA {extent['lba']:,} "
                                          f"→ Byte offset {extent['byte_offset']:,}")
                                    print(f"             → Size: {extent['size_bytes']:,} bytes")
                            
                            print(f"\nSummary:")
                            print(f"  Total clusters: {total_clusters:,}")
                            print(f"  Allocated clusters: {allocated_clusters:,}")
                            print(f"  Sparse clusters: {total_clusters - allocated_clusters:,}")
                        else:
                            print("No extents found (empty file)")
                else:
                    print("Could not determine residency status")
                    if 'residency_error' in analysis:
                        print(f"Error: {analysis['residency_error']}")
            
        except Exception as e:
            print(f"Error: {e}")

def print_usage():
    """Print usage information"""
    print("NTFS LBA Analysis and Manipulation Tool")
    print("=" * 50)
    print("Comprehensive tool for NTFS file system analysis and LBA operations")
    print()
    print("Features:")
    print("- File to LBA mapping (VCN → LCN → LBA)")
    print("- MFT record analysis and fetching")
    print("- File residency detection")
    print("- Direct LBA reading and writing")
    print("- Partition information retrieval")
    print()
    print("Usage:")
    print("  python ntfs_lba_tool.py <file_path>           # Analyze file")
    print("  python ntfs_lba_tool.py mft:<record>:<drive>  # Analyze MFT record")
    print("  python ntfs_lba_tool.py lba:<drive>:<lba>     # Read LBA")
    print("  python ntfs_lba_tool.py                       # Interactive mode")
    print()
    print("Examples:")
    print("  python ntfs_lba_tool.py \"C:\\Windows\\notepad.exe\"")
    print("  python ntfs_lba_tool.py mft:5:C")
    print("  python ntfs_lba_tool.py lba:0:2048")
    print()
    print("Requires Administrator privileges for write operations and MFT access.")
    print()

def main():
    """Main function"""
    tool = NTFSLBATool()
    
    print_usage()
    
    # Check admin privileges
    if not tool.is_admin():
        print("⚠️  WARNING: Not running as Administrator.")
        print("   Some operations may fail without Administrator privileges.\n")
    else:
        print("✓ Running with Administrator privileges\n")
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg.startswith("mft:"):
            # MFT record analysis: mft:record_number:drive
            try:
                parts = arg.split(":")
                if len(parts) >= 3:
                    record_num = int(parts[1])
                    drive = parts[2].upper()
                    
                    print(f"Fetching MFT record {record_num} from drive {drive}:")
                    print("=" * 60)
                    
                    mft_data = tool.fetch_mft_record(drive, record_num)
                    print(f"Successfully read {len(mft_data)} bytes")
                    
                    header = tool.analyze_mft_record(mft_data)
                    print(f"\nSignature: {header['signature']} ({'✓ Valid' if header['signature_valid'] else '✗ INVALID'})")
                    print(f"In Use: {'Yes' if header['is_in_use'] else 'No'}")
                    print(f"Is Directory: {'Yes' if header['is_directory'] else 'No'}")
                    print(f"Sequence Number: {header['sequence_number']}")
                    print(f"Link Count: {header['link_count']}")
                    print(f"Bytes in Use: {header['bytes_in_use']}")
                    
                    if header['data_attributes']:
                        print(f"\n$DATA Attributes: {len(header['data_attributes'])}")
                        for i, attr in enumerate(header['data_attributes']):
                            status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                            stream_info = f" ('{attr['stream_name']}') " if attr['stream_name'] else " (unnamed) "
                            print(f"  Attribute {i+1}: {status}{stream_info}")
                    
                    if "--hex" in sys.argv or "-x" in sys.argv:
                        print(f"\nHex dump (first 256 bytes):")
                        print(tool.hex_dump(mft_data, 0, 256))
                else:
                    print("Usage: mft:record_number:drive")
            except Exception as e:
                print(f"Error: {e}")
        
        elif arg.startswith("lba:"):
            # LBA reading: lba:drive_number:lba
            try:
                parts = arg.split(":")
                if len(parts) >= 3:
                    drive_num = int(parts[1])
                    lba = int(parts[2])
                    
                    print(f"Reading LBA {lba} from PhysicalDrive{drive_num}:")
                    print("=" * 60)
                    
                    data = tool.read_lba(drive_num, lba, 512)
                    print(f"Successfully read {len(data)} bytes")
                    
                    print(f"\nHex dump:")
                    print(tool.hex_dump(data, 0, 256))
                    
                    # Try to detect if it's an MFT record
                    if data[:4] == b'FILE':
                        print(f"\n*** Detected MFT record signature ***")
                        try:
                            header = tool.analyze_mft_record(data)
                            print(f"MFT Record - In Use: {'Yes' if header['is_in_use'] else 'No'}")
                            print(f"Is Directory: {'Yes' if header['is_directory'] else 'No'}")
                        except:
                            pass
                else:
                    print("Usage: lba:drive_number:lba")
            except Exception as e:
                print(f"Error: {e}")
        
        else:
            # File analysis
            file_path = arg
            try:
                tool.print_file_analysis(file_path)
            except Exception as e:
                print(f"Error: {e}")
    
    else:
        # Interactive mode
        while True:
            try:
                print("\nOptions:")
                print("1. Analyze file or folder")
                print("2. Fetch MFT record")
                print("3. Read LBA")
                print("4. Write LBA (Admin required)")
                print("5. Check file residency")
                print("6. Quit")
                
                choice = input("\nChoose option (1-6): ").strip()
                
                if choice == "1":
                    path = input("Enter file or folder path: ").strip()
                    if path:
                        if path.startswith('"') and path.endswith('"'):
                            path = path[1:-1]
                        try:
                            tool.print_file_analysis(path)
                        except Exception as e:
                            print(f"Error: {e}")
                
                elif choice == "2":
                    try:
                        record_num = int(input("Enter MFT record number: ").strip())
                        drive = input("Enter drive letter (default C): ").strip().upper() or "C"
                        show_hex = input("Show hex dump? (y/n, default n): ").strip().lower().startswith('y')
                        
                        print(f"\nFetching MFT record {record_num} from drive {drive}:")
                        print("=" * 50)
                        
                        mft_data = tool.fetch_mft_record(drive, record_num)
                        header = tool.analyze_mft_record(mft_data)
                        
                        print(f"Signature: {header['signature']} ({'✓ Valid' if header['signature_valid'] else '✗ INVALID'})")
                        print(f"In Use: {'Yes' if header['is_in_use'] else 'No'}")
                        print(f"Is Directory: {'Yes' if header['is_directory'] else 'No'}")
                        
                        if show_hex:
                            print(f"\nHex dump:")
                            print(tool.hex_dump(mft_data, 0, 256))
                    except ValueError:
                        print("Invalid MFT record number")
                    except Exception as e:
                        print(f"Error: {e}")
                
                elif choice == "3":
                    try:
                        drive_num = int(input("Enter physical drive number: ").strip())
                        lba = int(input("Enter LBA: ").strip())
                        
                        print(f"\nReading LBA {lba} from PhysicalDrive{drive_num}:")
                        print("=" * 50)
                        
                        data = tool.read_lba(drive_num, lba, 512)
                        print(f"Successfully read {len(data)} bytes")
                        print(f"\nHex dump:")
                        print(tool.hex_dump(data, 0, 256))
                    except ValueError:
                        print("Invalid drive number or LBA")
                    except Exception as e:
                        print(f"Error: {e}")
                
                elif choice == "4":
                    if not tool.is_admin():
                        print("Administrator privileges required for write operations")
                        continue
                    
                    try:
                        drive_num = int(input("Enter physical drive number: ").strip())
                        lba = int(input("Enter LBA: ").strip())
                        data = input("Enter data to write: ").strip()
                        
                        print(f"\n⚠️  WARNING: This will write to PhysicalDrive{drive_num}, LBA {lba}")
                        print(f"Data: {data}")
                        confirm = input("Type 'YES' to confirm: ")
                        
                        if confirm == "YES":
                            bytes_written = tool.write_lba(drive_num, lba, data)
                            print(f"Successfully wrote {bytes_written} bytes")
                        else:
                            print("Cancelled")
                    except ValueError:
                        print("Invalid input")
                    except Exception as e:
                        print(f"Error: {e}")
                
                elif choice == "5":
                    path = input("Enter file path: ").strip()
                    if path:
                        if path.startswith('"') and path.endswith('"'):
                            path = path[1:-1]
                        try:
                            is_resident = tool.is_file_resident(path)
                            file_size = os.path.getsize(path)
                            print(f"\nFile: {path}")
                            print(f"Size: {file_size:,} bytes")
                            print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
                        except Exception as e:
                            print(f"Error: {e}")
                
                elif choice == "6" or choice.lower() in ['quit', 'exit', 'q']:
                    break
                else:
                    print("Invalid option")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)