import ctypes
import os
import sys
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = -1

# Attribute types
ATTR_STANDARD_INFORMATION = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME = 0x30
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_INDEX_ALLOCATION = 0xA0
ATTR_END = 0xFFFFFFFF

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

class NTFSError(Exception):
    """Custom exception for NTFS-related errors"""
    pass

def safe_handle_close(handle):
    """Safely close a handle if it's valid"""
    if handle and handle != INVALID_HANDLE_VALUE:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except:
            pass  # Ignore errors when closing

def open_file(path):
    """Open a file handle with proper error handling"""
    try:
        # Use \\?\ prefix for long path support
        abs_path = os.path.abspath(path)
        if not abs_path.startswith("\\\\?\\"):
            abs_path = r"\\?\{}".format(abs_path)
        
        handle = ctypes.windll.kernel32.CreateFileW(
            abs_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,  # Required for directories
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)
        return handle
    except Exception as e:
        raise NTFSError(f"Failed to open '{path}': {e}")

def open_volume(drive_letter):
    """Open a volume handle with proper error handling"""
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
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)
        return handle
    except Exception as e:
        raise NTFSError(f"Failed to open volume '{drive_letter}:': {e}")

def get_ntfs_volume_data(vol_handle):
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
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)
        
        # Validate the returned data
        if vol_info.BytesPerFileRecordSegment == 0:
            raise NTFSError("Invalid NTFS volume data returned")
            
        return vol_info
    except Exception as e:
        raise NTFSError(f"Failed to get NTFS volume data: {e}")

def get_partition_start_lba(drive_letter):
    """Get partition starting LBA"""
    handle = None
    try:
        volume_path = r"\\.\{}:".format(drive_letter.upper())
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path,
            0,  # No access needed for this IOCTL
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if handle == INVALID_HANDLE_VALUE:
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)

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
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)

        # Use 512 as default sector size for LBA calculation
        starting_lba = part_info.StartingOffset // 512
        return starting_lba
        
    except Exception as e:
        raise NTFSError(f"Failed to get partition start LBA: {e}")
    finally:
        safe_handle_close(handle)

def get_sectors_per_cluster(drive_letter):
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
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)

        return sectors_per_cluster.value, bytes_per_sector.value
    except Exception as e:
        raise NTFSError(f"Failed to get cluster information: {e}")

def fetch_mft_record_raw(drive_letter, mft_record_number):
    """
    Fetch raw MFT record data directly from disk.
    
    Args:
        drive_letter: Drive letter (e.g., 'C')
        mft_record_number: MFT record number to fetch
        
    Returns:
        bytes: Raw MFT record data
    """
    vol_handle = None
    
    try:
        # Validate inputs
        if not isinstance(mft_record_number, int) or mft_record_number < 0:
            raise NTFSError(f"Invalid MFT record number: {mft_record_number}")
        
        if mft_record_number > 100000000:  # Reasonable upper bound
            raise NTFSError(f"MFT record number too large: {mft_record_number}")
        
        # Open volume and get NTFS information
        vol_handle = open_volume(drive_letter)
        vol_info = get_ntfs_volume_data(vol_handle)
        
        # Calculate MFT record offset
        mft_start_byte_offset = vol_info.MftStartLcn * vol_info.BytesPerCluster
        record_byte_offset = mft_record_number * vol_info.BytesPerFileRecordSegment
        absolute_offset = mft_start_byte_offset + record_byte_offset
        
        # Set file pointer to MFT record location
        high = ctypes.c_long(absolute_offset >> 32)
        low = ctypes.c_long(absolute_offset & 0xFFFFFFFF)
        
        result = ctypes.windll.kernel32.SetFilePointer(
            vol_handle, low, ctypes.byref(high), 0  # FILE_BEGIN
        )
        
        if result == INVALID_HANDLE_VALUE:
            error_code = ctypes.windll.kernel32.GetLastError()
            if error_code != 0:  # Only raise if there's actually an error
                raise ctypes.WinError(error_code)
        
        # Read MFT record
        record_size = vol_info.BytesPerFileRecordSegment
        buffer = ctypes.create_string_buffer(record_size)
        bytes_read = wintypes.DWORD()
        
        success = ctypes.windll.kernel32.ReadFile(
            vol_handle, buffer, record_size, ctypes.byref(bytes_read), None
        )
        
        if not success:
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)
        
        if bytes_read.value != record_size:
            raise NTFSError(f"Read {bytes_read.value} bytes, expected {record_size}")
        
        return buffer.raw
        
    except Exception as e:
        raise NTFSError(f"Failed to fetch MFT record {mft_record_number}: {e}")
    finally:
        safe_handle_close(vol_handle)

def dump_mft_record_hex(mft_data, bytes_per_line=16, max_lines=32):
    """
    Dump MFT record data in hex format for debugging.
    
    Args:
        mft_data: Raw MFT record bytes
        bytes_per_line: Number of bytes to display per line
        max_lines: Maximum lines to show (0 = show all)
    """
    if not mft_data:
        print("No MFT data to display")
        return
        
    print(f"MFT Record Size: {len(mft_data)} bytes")
    print("Hex Dump:")
    print("-" * 80)
    
    total_lines = len(mft_data) // bytes_per_line + (1 if len(mft_data) % bytes_per_line else 0)
    lines_to_show = min(total_lines, max_lines) if max_lines > 0 else total_lines
    
    for line in range(lines_to_show):
        i = line * bytes_per_line
        # Offset
        print(f"{i:04x}: ", end="")
        
        # Hex bytes
        hex_part = ""
        ascii_part = ""
        for j in range(bytes_per_line):
            if i + j < len(mft_data):
                byte_val = mft_data[i + j]
                hex_part += f"{byte_val:02x} "
                # ASCII representation
                if 32 <= byte_val <= 126:
                    ascii_part += chr(byte_val)
                else:
                    ascii_part += "."
            else:
                hex_part += "   "
                ascii_part += " "
        
        print(f"{hex_part} | {ascii_part}")
    
    if max_lines > 0 and total_lines > max_lines:
        print(f"... ({total_lines - max_lines} more lines)")

def analyze_mft_record_header(mft_data):
    """
    Analyze and display MFT record header information.
    
    Args:
        mft_data: Raw MFT record bytes
        
    Returns:
        dict: Parsed header information or None if invalid
    """
    if len(mft_data) < 48:
        raise NTFSError(f"MFT record too small: {len(mft_data)} bytes (need at least 48)")
    
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
            raise NTFSError(f"Invalid attributes offset: {attrs_offset}")
        
        if bytes_in_use > len(mft_data):
            raise NTFSError(f"Invalid bytes_in_use: {bytes_in_use}")
        
        # Decode flags
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
        
        return header_info
        
    except Exception as e:
        raise NTFSError(f"Failed to parse MFT record header: {e}")

def parse_mft_attributes(mft_data):
    """Parse MFT record to find $DATA attribute and check residency"""
    try:
        # First analyze the header
        header = analyze_mft_record_header(mft_data)
        
        if not header['signature_valid']:
            if header['signature'] == b'\x00\x00\x00\x00':
                raise NTFSError("MFT record is free/unused (null signature)")
            elif header['signature'] == b'BAAD':
                raise NTFSError("MFT record is marked as bad")
            else:
                raise NTFSError(f"Invalid MFT signature: {header['signature'].hex().upper()} (expected FILE)")
        
        if not header['is_in_use']:
            raise NTFSError("MFT record is not marked as in use")
        
        # Scan attributes
        offset = header['attrs_offset']
        data_attributes = []
        attr_count = 0
        
        while offset < len(mft_data) - 8 and attr_count < 50:  # Safety limit
            # Read attribute type
            if offset + 4 > len(mft_data):
                break
                
            attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
            
            # End of attributes
            if attr_type == ATTR_END or attr_type == 0:
                break
            
            # Read attribute length
            if offset + 8 > len(mft_data):
                break
                
            attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
            
            # Validate attribute length
            if attr_length < 8 or attr_length > len(mft_data) - offset or attr_length % 4 != 0:
                break  # Invalid attribute, stop parsing
            
            # Check if this is a $DATA attribute
            if attr_type == ATTR_DATA:
                # Read non-resident flag (at offset 8 from attribute start)
                if offset + 9 <= len(mft_data):
                    non_resident_flag = mft_data[offset + 8]
                    
                    # Get attribute name length and name offset for named streams
                    name_length = mft_data[offset + 9] if offset + 9 < len(mft_data) else 0
                    name_offset = int.from_bytes(mft_data[offset + 10:offset + 12], "little") if offset + 12 <= len(mft_data) else 0
                    
                    stream_name = ""
                    if name_length > 0 and name_offset > 0 and offset + name_offset + name_length * 2 <= len(mft_data):
                        # Extract UTF-16 name
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
        raise NTFSError(f"Failed to parse MFT attributes: {e}")

def get_file_extents(file_handle):
    """Get file extents (VCN → LCN mapping) for non-resident files"""
    try:
        input_buffer = STARTING_VCN_INPUT_BUFFER(0)
        out_size = 8192  # Increased buffer size
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
            error_code = ctypes.windll.kernel32.GetLastError()
            if error_code == 1:  # ERROR_INVALID_FUNCTION - file is resident
                return None
            elif error_code == 87:  # ERROR_INVALID_PARAMETER - might be a directory
                return None
            else:
                raise ctypes.WinError(error_code)

        # Validate buffer size
        if returned.value < 16:  # Need at least header
            return None
        
        # Parse extent data
        extent_count = int.from_bytes(output_buffer[0:4], 'little')
        starting_vcn = int.from_bytes(output_buffer[8:16], 'little')
        
        # Sanity check extent count
        if extent_count == 0:
            return []
        
        if extent_count > 1000:  # Reasonable limit
            raise NTFSError(f"ExtentCount {extent_count} seems too large")
        
        # Verify we have enough data for all extents
        expected_size = 16 + extent_count * 16
        if returned.value < expected_size:
            raise NTFSError(f"Buffer size {returned.value} too small for {extent_count} extents")
        
        extents = []
        current_vcn = starting_vcn
        
        for i in range(extent_count):
            offset = 16 + i * 16
            
            next_vcn = int.from_bytes(output_buffer[offset:offset+8], 'little')
            lcn_raw = output_buffer[offset+8:offset+16]
            
            # Check for sparse extent (all FF bytes means sparse/unallocated)
            if lcn_raw == b'\xff' * 8:
                lcn = -1  # Sparse
            else:
                lcn = int.from_bytes(lcn_raw, 'little', signed=True)
                # Additional validation for LCN
                if lcn < 0 and lcn != -1:
                    lcn = -1  # Treat negative LCNs as sparse
            
            # Validate VCN progression
            if next_vcn <= current_vcn:
                break  # Invalid extent data
            
            extents.append((current_vcn, next_vcn, lcn))
            current_vcn = next_vcn

        return extents
        
    except Exception as e:
        # Return None instead of raising for non-critical errors
        return None

def get_file_info_safe(file_path):
    """
    Safely get file information including MFT record number.
    
    Returns:
        dict: File information or None if failed
    """
    file_handle = None
    
    try:
        file_handle = open_file(file_path)
        
        file_info = BY_HANDLE_FILE_INFORMATION()
        success = ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        )
        
        if not success:
            error_code = ctypes.windll.kernel32.GetLastError()
            raise ctypes.WinError(error_code)
        
        # Calculate file index and MFT record number
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        
        # For NTFS, MFT record number is in lower 48 bits
        mft_record_number = file_index & 0xFFFFFFFFFFFF
        sequence_number = (file_index >> 48) & 0xFFFF
        
        # Validate MFT record number is reasonable
        if mft_record_number > 100000000:
            raise NTFSError(f"MFT record number {mft_record_number} seems invalid")
        
        result = {
            "file_index": file_index,
            "mft_record_number": mft_record_number,
            "sequence_number": sequence_number,
            "volume_serial": file_info.dwVolumeSerialNumber,
            "file_size": (file_info.nFileSizeHigh << 32) | file_info.nFileSizeLow,
            "attributes": file_info.dwFileAttributes,
            "link_count": file_info.nNumberOfLinks
        }
        
        return result
        
    except Exception as e:
        raise NTFSError(f"Failed to get file information: {e}")
    finally:
        safe_handle_close(file_handle)

def calculate_mft_record_lba(drive_letter, mft_record_number, vol_info, partition_start_lba):
    """Calculate the LBA of an MFT record"""
    try:
        # Calculate MFT record location
        mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
        mft_record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
        mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
        
        # Convert to LBA (using 512 byte sectors)
        mft_record_lba_relative = mft_record_absolute_offset // 512
        mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
        
        return {
            "mft_record_lba_relative": mft_record_lba_relative,
            "mft_record_lba_absolute": mft_record_lba_absolute,
            "mft_record_byte_offset": mft_record_absolute_offset
        }
        
    except Exception as e:
        raise NTFSError(f"Error calculating MFT record LBA: {e}")

def fetch_and_analyze_mft_record(drive_letter, mft_record_number, show_hex_dump=False):
    """
    Fetch and analyze an MFT record, showing detailed information.
    
    Args:
        drive_letter: Drive letter (e.g., 'C')
        mft_record_number: MFT record number to analyze
        show_hex_dump: Whether to show hex dump of the record
    """
    try:
        print(f"Fetching MFT record {mft_record_number} from drive {drive_letter}:")
        print("=" * 60)
        
        # Get volume info first
        vol_handle = open_volume(drive_letter)
        vol_info = get_ntfs_volume_data(vol_handle)
        safe_handle_close(vol_handle)
        
        partition_start_lba = get_partition_start_lba(drive_letter)
        
        # Calculate LBA information
        lba_info = calculate_mft_record_lba(drive_letter, mft_record_number, vol_info, partition_start_lba)
        
        print(f"MFT Record Number: {mft_record_number}")
        print(f"MFT Record LBA (relative): {lba_info['mft_record_lba_relative']:,}")
        print(f"MFT Record LBA (absolute): {lba_info['mft_record_lba_absolute']:,}")
        print(f"MFT Record Byte Offset: {lba_info['mft_record_byte_offset']:,}")
        print()
        
        # Fetch raw MFT record
        try:
            mft_data = fetch_mft_record_raw(drive_letter, mft_record_number)
            print(f"Successfully read {len(mft_data)} bytes")
            print()
        except Exception as e:
            print(f"Failed to read MFT record: {e}")
            return None
        
        # Show hex dump if requested
        if show_hex_dump:
            print("=== Raw MFT Record Data ===")
            dump_mft_record_hex(mft_data, 16, 32)  # Show first 32 lines
            print()
        
        # Analyze header
        print("=== MFT Record Header ===")
        try:
            header = analyze_mft_record_header(mft_data)
            
            print(f"Signature: {header['signature']} ({'✓ Valid' if header['signature_valid'] else '✗ INVALID'})")
            
            if header['signature_valid']:
                print(f"Sequence Number: {header['sequence_number']}")
                print(f"Link Count: {header['link_count']}")
                print(f"Flags: 0x{header['flags']:04x} ({header['flags_description']})")
                print(f"In Use: {'Yes' if header['is_in_use'] else 'No'}")
                print(f"Is Directory: {'Yes' if header['is_directory'] else 'No'}")
                print(f"First Attribute Offset: {header['attrs_offset']}")
                print(f"Bytes in Use: {header['bytes_in_use']}")
                print(f"Bytes Allocated: {header['bytes_allocated']}")
                
                if header['base_record'] != 0:
                    print(f"Base Record: {header['base_record']} (this is an extension record)")
                
                print()
                
                # Analyze attributes if valid and in use
                if header['is_in_use']:
                    print("=== Attributes Analysis ===")
                    try:
                        data_attributes = parse_mft_attributes(mft_data)
                        if data_attributes:
                            for i, attr in enumerate(data_attributes):
                                status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                                stream_info = f" ('{attr['stream_name']}')" if attr['stream_name'] else " (unnamed)"
                                print(f"$DATA attribute {i+1}: {status}{stream_info}")
                        else:
                            if header['is_directory']:
                                print("No $DATA attributes (this is a directory)")
                            else:
                                print("No $DATA attributes found")
                    except Exception as e:
                        print(f"Error parsing attributes: {e}")
                else:
                    print("Record not in use - skipping attribute analysis")
            else:
                print("Invalid signature - cannot parse attributes")
                
        except Exception as e:
            print(f"Error analyzing header: {e}")
            print("\nShowing first 64 bytes as hex for debugging:")
            dump_mft_record_hex(mft_data[:64], 16)
        
        return mft_data
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def analyze_path(path):
    """Comprehensive analysis of a file or folder"""
    vol_handle = None
    
    try:
        # Validate input
        if not os.path.exists(path):
            raise NTFSError(f"Path does not exist: {path}")
        
        # Get drive letter
        drive_letter = os.path.splitdrive(path)[0].replace(":", "").upper()
        if not drive_letter:
            raise NTFSError("Could not determine drive letter")
        
        # Check if it's an NTFS volume
        try:
            vol_handle = open_volume(drive_letter)
            vol_info = get_ntfs_volume_data(vol_handle)
            safe_handle_close(vol_handle)
            vol_handle = None
        except Exception as e:
            raise NTFSError(f"Not an NTFS volume or cannot access: {e}")
        
        # Get file information
        try:
            file_info = get_file_info_safe(path)
        except Exception as e:
            raise NTFSError(f"Cannot get file information: {e}")
        
        # Get partition and cluster information
        try:
            partition_start_lba = get_partition_start_lba(drive_letter)
            sectors_per_cluster, bytes_per_sector = get_sectors_per_cluster(drive_letter)
        except Exception as e:
            raise NTFSError(f"Cannot get disk geometry: {e}")
        
        # Calculate MFT record LBA
        lba_info = calculate_mft_record_lba(
            drive_letter, file_info['mft_record_number'], vol_info, partition_start_lba
        )
        
        # Determine if path is directory or file
        is_directory = os.path.isdir(path)
        file_size = 0 if is_directory else os.path.getsize(path)
        
        # Print comprehensive analysis
        print("=" * 80)
        print(f"NTFS Analysis for: {path}")
        print("=" * 80)
        
        # Basic information
        print(f"Type: {'Directory' if is_directory else 'File'}")
        if not is_directory:
            print(f"Size: {file_size:,} bytes")
        print(f"Drive: {drive_letter}:")
        print(f"Volume Serial: 0x{file_info['volume_serial']:08X}")
        print()
        
        # MFT Record Information
        print("=== MFT Record Information ===")
        print(f"MFT Record Number: {file_info['mft_record_number']:,}")
        print(f"Sequence Number: {file_info['sequence_number']}")
        print(f"File Index: 0x{file_info['file_index']:016X}")
        print(f"MFT Record LBA (relative): {lba_info['mft_record_lba_relative']:,}")
        print(f"MFT Record LBA (absolute): {lba_info['mft_record_lba_absolute']:,}")
        print(f"MFT Record Byte Offset: {lba_info['mft_record_byte_offset']:,}")
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
        
        # Analyze MFT record and file data
        print("=== MFT Record Analysis ===")
        try:
            mft_data = fetch_mft_record_raw(drive_letter, file_info['mft_record_number'])
            header = analyze_mft_record_header(mft_data)
            
            print(f"Signature: {header['signature']} ({'✓ Valid' if header['signature_valid'] else '✗ INVALID'})")
            print(f"Record Status: {'In Use' if header['is_in_use'] else 'Free/Unused'}")
            print(f"Record Type: {'Directory' if header['is_directory'] else 'File'}")
            print(f"Sequence Number: {header['sequence_number']} (File: {file_info['sequence_number']})")
            
            if header['sequence_number'] != file_info['sequence_number']:
                print("⚠️  WARNING: Sequence number mismatch - file may have been deleted/recreated")
            
            print()
            
            # Analyze file data if it's a valid, in-use file record
            if header['signature_valid'] and header['is_in_use'] and not is_directory:
                print("=== File Data Analysis ===")
                try:
                    data_attributes = parse_mft_attributes(mft_data)
                    
                    if not data_attributes:
                        print("No $DATA attributes found")
                    else:
                        # Analyze each $DATA attribute
                        for i, attr in enumerate(data_attributes):
                            stream_name = attr['stream_name'] if attr['stream_name'] else "(unnamed/default)"
                            print(f"\n$DATA Stream {i+1}: {stream_name}")
                            
                            if attr['is_resident']:
                                print("  Status: RESIDENT (data stored in MFT record)")
                                print("  Location: Data is embedded within this MFT record")
                            else:
                                print("  Status: NON-RESIDENT (data stored in disk clusters)")
                                
                                # Get file extents
                                file_handle = open_file(path)
                                extents = get_file_extents(file_handle)
                                safe_handle_close(file_handle)
                                
                                if extents is None:
                                    print("  ⚠️  Could not retrieve file extents")
                                elif len(extents) == 0:
                                    print("  File has no allocated extents (empty file)")
                                else:
                                    print(f"  Extents: {len(extents)} extent(s)")
                                    print("\n  VCN → LCN → LBA Mapping:")
                                    
                                    total_clusters = 0
                                    allocated_clusters = 0
                                    
                                    for j, (start_vcn, next_vcn, lcn) in enumerate(extents):
                                        cluster_count = next_vcn - start_vcn
                                        total_clusters += cluster_count
                                        
                                        if lcn == -1:
                                            print(f"    Extent {j+1}: VCN {start_vcn:,}-{next_vcn-1:,} ({cluster_count:,} clusters) → SPARSE")
                                        else:
                                            allocated_clusters += cluster_count
                                            # Calculate absolute LBA
                                            lcn_relative_lba = lcn * sectors_per_cluster
                                            absolute_lba = partition_start_lba + lcn_relative_lba
                                            byte_offset = absolute_lba * bytes_per_sector
                                            size_bytes = cluster_count * vol_info.BytesPerCluster
                                            
                                            print(f"    Extent {j+1}: VCN {start_vcn:,}-{next_vcn-1:,} ({cluster_count:,} clusters)")
                                            print(f"              → LCN {lcn:,} → LBA {absolute_lba:,} → Byte offset {byte_offset:,}")
                                            print(f"              → Size: {size_bytes:,} bytes")
                                    
                                    print(f"\n  Summary:")
                                    print(f"    Total clusters: {total_clusters:,}")
                                    print(f"    Allocated clusters: {allocated_clusters:,}")
                                    print(f"    Sparse clusters: {total_clusters - allocated_clusters:,}")
                                    total_allocated_bytes = allocated_clusters * vol_info.BytesPerCluster
                                    print(f"    Total allocated size: {total_allocated_bytes:,} bytes")
                        
                        # Show summary
                        resident_count = sum(1 for attr in data_attributes if attr['is_resident'])
                        nonresident_count = len(data_attributes) - resident_count
                        print(f"\nData Streams Summary: {len(data_attributes)} total ({resident_count} resident, {nonresident_count} non-resident)")
                        
                except Exception as e:
                    print(f"Error analyzing file data: {e}")
            
            elif is_directory and header['signature_valid'] and header['is_in_use']:
                print("=== Directory Analysis ===")
                print("This is a directory - data is stored in $INDEX_ROOT and $INDEX_ALLOCATION attributes")
                
        except Exception as e:
            print(f"Error reading/analyzing MFT record: {e}")
            print("\nTrying to fetch raw MFT data for debugging...")
            try:
                raw_data = fetch_mft_record_raw(drive_letter, file_info['mft_record_number'])
                print(f"Raw MFT record size: {len(raw_data)} bytes")
                print("First 32 bytes (hex):")
                dump_mft_record_hex(raw_data[:32], 16)
            except Exception as e2:
                print(f"Could not fetch raw MFT data: {e2}")
        
        # Show calculation breakdown
        print("\n=== MFT Record LBA Calculation ===")
        print(f"1. MFT starts at LCN {vol_info.MftStartLcn:,}")
        print(f"2. MFT byte offset = {vol_info.MftStartLcn:,} × {vol_info.BytesPerCluster:,} = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,}")
        print(f"3. Record {file_info['mft_record_number']:,} offset = {file_info['mft_record_number']:,} × {vol_info.BytesPerFileRecordSegment:,} = {file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,}")
        print(f"4. Total offset = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,} + {file_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,} = {lba_info['mft_record_byte_offset']:,}")
        print(f"5. Relative LBA = {lba_info['mft_record_byte_offset']:,} ÷ 512 = {lba_info['mft_record_lba_relative']:,}")
        print(f"6. Absolute LBA = {partition_start_lba:,} + {lba_info['mft_record_lba_relative']:,} = {lba_info['mft_record_lba_absolute']:,}")
        
    except Exception as e:
        raise NTFSError(f"Error analyzing path: {e}")
    finally:
        safe_handle_close(vol_handle)

def print_usage():
    """Print usage information"""
    print("NTFS File and MFT Analyzer")
    print("=" * 40)
    print("Analyzes NTFS files and directories, showing:")
    print("- MFT record number and LBA location")
    print("- File residency status (resident vs non-resident)")
    print("- File extent mapping (VCN → LCN → LBA) for non-resident files")
    print("- Raw MFT record analysis and debugging")
    print()
    print("Usage:")
    print("  python ntfs_analyzer.py <file_or_folder_path>")
    print("  python ntfs_analyzer.py mft:<record_number>:<drive> [--hex]")
    print("  python ntfs_analyzer.py  (interactive mode)")
    print()
    print("Examples:")
    print("  python ntfs_analyzer.py \"C:\\Windows\\notepad.exe\"")
    print("  python ntfs_analyzer.py mft:5:C --hex")
    print()
    print("Requires Administrator privileges for low-level disk access.")
    print()

def test_common_files():
    """Test with some common files to verify functionality"""
    print("\n" + "=" * 60)
    print("Testing with common system files:")
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
                analyze_path(test_file)
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
            fetch_and_analyze_mft_record("C", record_num, False)
        except Exception as e:
            print(f"Error accessing MFT record {record_num}: {e}")

def main():
    """Main function with improved error handling and debugging"""
    print_usage()
    
    # Check if running as administrator
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("⚠️  WARNING: Not running as Administrator. Some operations may fail.")
            print("   For full functionality, run as Administrator.\n")
    except:
        print("⚠️  Cannot determine admin status.\n")
    
    if len(sys.argv) > 1:
        # Check for MFT record direct access
        if sys.argv[1].startswith("mft:"):
            try:
                parts = sys.argv[1].split(":")
                if len(parts) >= 3:  # mft:record_number:drive
                    record_num = int(parts[1])
                    drive = parts[2].upper()
                    show_hex = "--hex" in sys.argv[2:] or "-x" in sys.argv[2:]
                    fetch_and_analyze_mft_record(drive, record_num, show_hex)
                else:
                    print("Usage for MFT record: mft:record_number:drive [--hex]")
                    print("Example: python ntfs_analyzer.py mft:5:C --hex")
                return
            except ValueError:
                print("Error: Invalid MFT record number")
                return
            except Exception as e:
                print(f"Error: {e}")
                return
        
        # Check for test mode
        if sys.argv[1] == "--test":
            test_common_files()
            return
        
        # Regular file/folder path analysis
        path = sys.argv[1]
        try:
            analyze_path(path)
        except Exception as e:
            print(f"Error: {e}")
            if "access" in str(e).lower() or "permission" in str(e).lower():
                print("💡 Try running as Administrator for full access to NTFS structures.")
    else:
        # Interactive mode
        while True:
            try:
                print("\nOptions:")
                print("1. Analyze file or folder path")
                print("2. Fetch raw MFT record by number")
                print("3. Run tests on common files")
                print("4. Quit")
                
                choice = input("\nChoose option (1-4): ").strip()
                
                if choice == "1":
                    path = input("Enter file or folder path: ").strip()
                    if path:
                        # Remove quotes if present
                        if path.startswith('"') and path.endswith('"'):
                            path = path[1:-1]
                        try:
                            analyze_path(path)
                        except Exception as e:
                            print(f"Error: {e}")
                            if "access" in str(e).lower() or "permission" in str(e).lower():
                                print("💡 Try running as Administrator.")
                
                elif choice == "2":
                    try:
                        record_num = int(input("Enter MFT record number: ").strip())
                        drive = input("Enter drive letter (default C): ").strip().upper() or "C"
                        show_hex = input("Show hex dump? (y/n, default n): ").strip().lower().startswith('y')
                        print()
                        fetch_and_analyze_mft_record(drive, record_num, show_hex)
                    except ValueError:
                        print("Error: Invalid MFT record number")
                    except Exception as e:
                        print(f"Error: {e}")
                
                elif choice == "3":
                    test_common_files()
                
                elif choice == "4" or choice.lower() in ['quit', 'exit', 'q']:
                    break
                else:
                    print("Invalid option. Please choose 1-4.")
                    
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