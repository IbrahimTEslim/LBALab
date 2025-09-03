import ctypes
import os
import sys
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x70000
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = -1

# Partition styles
PARTITION_STYLE_MBR = 0
PARTITION_STYLE_GPT = 1
PARTITION_STYLE_RAW = 2

# Attribute types
ATTR_STANDARD_INFORMATION = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME = 0x30
ATTR_OBJECT_ID = 0x40
ATTR_SECURITY_DESCRIPTOR = 0x50
ATTR_VOLUME_NAME = 0x60
ATTR_VOLUME_INFORMATION = 0x70
ATTR_DATA = 0x80
ATTR_INDEX_ROOT = 0x90
ATTR_INDEX_ALLOCATION = 0xA0
ATTR_BITMAP = 0xB0
ATTR_REPARSE_POINT = 0xC0
ATTR_EA_INFORMATION = 0xD0
ATTR_EA = 0xE0
ATTR_PROPERTY_SET = 0xF0
ATTR_LOGGED_UTILITY_STREAM = 0x100
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
        ("PartitionType", ctypes.c_byte * 16),  # GUID
        ("PartitionId", ctypes.c_byte * 16),    # GUID
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

class DISK_GEOMETRY(ctypes.Structure):
    _fields_ = [
        ("Cylinders", ctypes.c_longlong),
        ("MediaType", wintypes.DWORD),
        ("TracksPerCylinder", wintypes.DWORD),
        ("SectorsPerTrack", wintypes.DWORD),
        ("BytesPerSector", wintypes.DWORD)
    ]

class RETRIEVAL_POINTERS_BUFFER(ctypes.Structure):
    _fields_ = [
        ("ExtentCount", ctypes.c_uint32),
        ("StartingVcn", ctypes.c_ulonglong),
    ]

class EXTENT_PAIR(ctypes.Structure):
    _fields_ = [
        ("NextVcn", ctypes.c_ulonglong),
        ("Lcn", ctypes.c_ulonglong),
    ]

class NTFSError(Exception):
    """Custom exception for NTFS-related errors"""
    pass

def safe_handle_close(handle):
    """Safely close a handle if it's valid"""
    if handle and handle != INVALID_HANDLE_VALUE:
        ctypes.windll.kernel32.CloseHandle(handle)

def open_file(path):
    """Open a file handle with proper error handling"""
    try:
        path = r"\\?\{}".format(os.path.abspath(path))
        handle = ctypes.windll.kernel32.CreateFileW(
            path,
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
        raise NTFSError(f"Failed to open file '{path}': {e}")

def open_volume(drive_letter):
    """Open a volume handle with proper error handling"""
    try:
        volume_path = r"\\.\{}:".format(drive_letter)
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
            raise ctypes.WinError()
        return vol_info
    except Exception as e:
        raise NTFSError(f"Failed to get NTFS volume data: {e}")

def get_partition_start_lba(drive_letter):
    """Get partition starting LBA"""
    try:
        volume_path = r"\\.\{}:".format(drive_letter)
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
        
        try:
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
        finally:
            safe_handle_close(handle)

        bytes_per_sector = 512
        starting_lba = part_info.StartingOffset // bytes_per_sector
        return starting_lba
    except Exception as e:
        raise NTFSError(f"Failed to get partition start LBA: {e}")

def get_sectors_per_cluster(drive_letter):
    """Get sectors per cluster and bytes per sector"""
    try:
        sectors_per_cluster = wintypes.DWORD()
        bytes_per_sector = wintypes.DWORD()
        free_clusters = wintypes.DWORD()
        total_clusters = wintypes.DWORD()

        res = ctypes.windll.kernel32.GetDiskFreeSpaceW(
            ctypes.c_wchar_p(drive_letter + ":\\"),
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters)
        )
        if not res:
            raise ctypes.WinError()

        return sectors_per_cluster.value, bytes_per_sector.value
    except Exception as e:
        raise NTFSError(f"Failed to get cluster information: {e}")

def read_mft_record(drive_letter, mft_start_lcn, bytes_per_cluster, mft_record_size, mft_index):
    """Read an MFT record from the volume"""
    handle = None
    try:
        handle = open_volume(drive_letter)
        
        # Calculate offset in bytes
        offset = (mft_start_lcn * bytes_per_cluster) + (mft_index * mft_record_size)
        
        # Set file pointer using 64-bit offset
        high = ctypes.c_long(offset >> 32)
        low = ctypes.c_long(offset & 0xFFFFFFFF)
        
        result = ctypes.windll.kernel32.SetFilePointer(handle, low, ctypes.byref(high), 0)
        if result == INVALID_HANDLE_VALUE and ctypes.windll.kernel32.GetLastError() != 0:
            raise ctypes.WinError()
        
        # Read MFT record
        buf = ctypes.create_string_buffer(mft_record_size)
        read = wintypes.DWORD()
        
        if not ctypes.windll.kernel32.ReadFile(handle, buf, mft_record_size, ctypes.byref(read), None):
            raise ctypes.WinError()
            
        if read.value != mft_record_size:
            raise NTFSError(f"Only read {read.value} bytes, expected {mft_record_size}")
            
        return buf.raw
        
    except Exception as e:
        raise NTFSError(f"Failed to read MFT record {mft_index}: {e}")
    finally:
        safe_handle_close(handle)

def parse_mft_attributes(mft_data):
    """Parse MFT record to find $DATA attribute and check residency"""
    try:
        # Debug: Show first 16 bytes of MFT record
        print(f"Debug: First 16 bytes of MFT record: {mft_data[:16].hex()}")
        
        # Verify MFT signature
        if len(mft_data) < 4 or mft_data[:4] != b'FILE':
            raise NTFSError("Invalid MFT record signature")
        
        # Get first attribute offset
        if len(mft_data) < 0x16:
            raise NTFSError("MFT record too small")
            
        first_attr_offset = int.from_bytes(mft_data[0x14:0x16], "little")
        
        if first_attr_offset >= len(mft_data):
            raise NTFSError("Invalid first attribute offset")
        
        # Scan attributes
        offset = first_attr_offset
        data_attributes = []
        
        while offset < len(mft_data) - 8:
            # Read attribute type
            attr_type = int.from_bytes(mft_data[offset:offset+4], "little")
            
            # End of attributes
            if attr_type == ATTR_END or attr_type == 0:
                break
            
            # Read attribute length
            if offset + 8 > len(mft_data):
                break
            attr_length = int.from_bytes(mft_data[offset+4:offset+8], "little")
            
            # Validate attribute length
            if attr_length == 0 or attr_length > len(mft_data) - offset:
                break
            
            # Check if this is a $DATA attribute
            if attr_type == ATTR_DATA:
                # Read non-resident flag (at offset 8 from attribute start)
                if offset + 9 <= len(mft_data):
                    non_resident_flag = mft_data[offset + 8]
                    data_attributes.append({
                        'offset': offset,
                        'is_resident': non_resident_flag == 0,
                        'length': attr_length
                    })
            
            # Move to next attribute
            offset += attr_length
        
        return data_attributes
        
    except Exception as e:
        raise NTFSError(f"Failed to parse MFT attributes: {e}")

def get_file_extents(file_handle):
    """Get file extents (VCN → LCN mapping)"""
    try:
        input_buffer = STARTING_VCN_INPUT_BUFFER(0)
        out_size = 4096
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

        # If error indicates file is resident, return None
        if not res:
            err = ctypes.GetLastError()
            if err == 1:  # ERROR_INVALID_FUNCTION - file is resident
                return None
            raise ctypes.WinError(err)

        # Parse manually with proper error checking
        if returned.value < 12:
            raise ValueError("Buffer too small for RETRIEVAL_POINTERS_BUFFER header")
        
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
            
            # Check for sparse extent (all FF bytes)
            if lcn_raw == b'\xff' * 8:
                lcn = -1
            else:
                lcn = int.from_bytes(lcn_raw, 'little')
            
            extents.append((current_vcn, next_vcn, lcn))
            current_vcn = next_vcn

        return extents
    except Exception as e:
        return None  # Assume resident if we can't get extents

def calculate_mft_record_lba(file_path, vol_info, partition_start_lba, sectors_per_cluster):
    """Calculate the LBA of a file's MFT record"""
    file_handle = None
    
    try:
        # Open file to get MFT record number
        file_handle = open_file(file_path)
        
        file_info = BY_HANDLE_FILE_INFORMATION()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            file_handle, ctypes.byref(file_info)
        ):
            raise ctypes.WinError()
        
        # Combine high and low parts to get the full file index
        file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
        mft_record_number = file_index & 0xFFFFFFFFFFFF
        sequence_number = (file_index >> 48) & 0xFFFF
        
        safe_handle_close(file_handle)
        file_handle = None
        
        # Calculate MFT record location
        mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
        mft_record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
        mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
        
        # Convert to LBA (relative to partition start)
        mft_record_lba_relative = mft_record_absolute_offset // vol_info.BytesPerSector
        mft_record_lba_absolute = partition_start_lba + mft_record_lba_relative
        
        return {
            "mft_record_number": mft_record_number,
            "sequence_number": sequence_number,
            "mft_record_lba_relative": mft_record_lba_relative,
            "mft_record_lba_absolute": mft_record_lba_absolute,
            "mft_record_byte_offset": mft_record_absolute_offset
        }
        
    except Exception as e:
        raise NTFSError(f"Error calculating MFT record LBA: {e}")
    finally:
        safe_handle_close(file_handle)

def analyze_path(path):
    """Comprehensive analysis of a file or folder"""
    file_handle = None
    vol_handle = None
    
    try:
        # Validate input
        if not os.path.exists(path):
            raise NTFSError(f"Path does not exist: {path}")
        
        # Get drive letter
        drive_letter = os.path.splitdrive(path)[0].replace(":", "")
        if not drive_letter:
            raise NTFSError("Could not determine drive letter")
        
        # Get volume and partition information
        vol_handle = open_volume(drive_letter)
        vol_info = get_ntfs_volume_data(vol_handle)
        safe_handle_close(vol_handle)
        vol_handle = None
        
        partition_start_lba = get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = get_sectors_per_cluster(drive_letter)
        
        # Calculate MFT record information
        mft_info = calculate_mft_record_lba(path, vol_info, partition_start_lba, sectors_per_cluster)
        
        # Basic file information
        is_directory = os.path.isdir(path)
        file_size = 0 if is_directory else os.path.getsize(path)
        
        # Print header
        print("=" * 80)
        print(f"NTFS Analysis for: {path}")
        print("=" * 80)
        
        # Basic information
        print(f"Type: {'Directory' if is_directory else 'File'}")
        if not is_directory:
            print(f"Size: {file_size:,} bytes")
        print(f"Drive: {drive_letter}:")
        print()
        
        # MFT Record Information
        print("=== MFT Record Information ===")
        print(f"MFT Record Number: {mft_info['mft_record_number']:,}")
        print(f"Sequence Number: {mft_info['sequence_number']}")
        print(f"MFT Record LBA (relative): {mft_info['mft_record_lba_relative']:,}")
        print(f"MFT Record LBA (absolute): {mft_info['mft_record_lba_absolute']:,}")
        print(f"MFT Record Byte Offset: {mft_info['mft_record_byte_offset']:,}")
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
                # Check if file is resident by reading MFT record
                mft_data = read_mft_record(
                    drive_letter,
                    vol_info.MftStartLcn,
                    vol_info.BytesPerCluster,
                    vol_info.BytesPerFileRecordSegment,
                    mft_info['mft_record_number']
                )
                
                data_attributes = parse_mft_attributes(mft_data)
                
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
                        file_handle = open_file(path)
                        extents = get_file_extents(file_handle)
                        safe_handle_close(file_handle)
                        file_handle = None
                        
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
                            print(f"Stream {i+1}: {status}")
                
            except Exception as e:
                print(f"=== File Data Status ===")
                print(f"Could not determine residency: {e}")
        
        print()
        print("=== MFT Record LBA Calculation ===")
        print(f"1. MFT starts at LCN {vol_info.MftStartLcn:,}")
        print(f"2. MFT byte offset = {vol_info.MftStartLcn:,} × {vol_info.BytesPerCluster:,} = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,}")
        print(f"3. Record {mft_info['mft_record_number']:,} offset = {mft_info['mft_record_number']:,} × {vol_info.BytesPerFileRecordSegment:,} = {mft_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,}")
        print(f"4. Total offset = {vol_info.MftStartLcn * vol_info.BytesPerCluster:,} + {mft_info['mft_record_number'] * vol_info.BytesPerFileRecordSegment:,} = {mft_info['mft_record_byte_offset']:,}")
        print(f"5. Relative LBA = {mft_info['mft_record_byte_offset']:,} ÷ {bytes_per_sector:,} = {mft_info['mft_record_lba_relative']:,}")
        print(f"6. Absolute LBA = {partition_start_lba:,} + {mft_info['mft_record_lba_relative']:,} = {mft_info['mft_record_lba_absolute']:,}")
        
    except Exception as e:
        raise NTFSError(f"Error analyzing path: {e}")
    finally:
        safe_handle_close(file_handle)
        safe_handle_close(vol_handle)

def print_usage():
    """Print usage information"""
    print("NTFS File and MFT Analyzer")
    print("=" * 40)
    print("Analyzes NTFS files and directories, showing:")
    print("- MFT record number and LBA location")
    print("- File residency status (resident vs non-resident)")
    print("- File extent mapping (VCN → LCN → LBA) for non-resident files")
    print("- Volume and partition information")
    print()
    print("Usage:")
    print("  python ntfs_analyzer.py <file_or_folder_path>")
    print("  python ntfs_analyzer.py  (interactive mode)")
    print()
    print("Requires Administrator privileges for low-level disk access.")
    print()

def main():
    """Main function"""
    print_usage()
    
    if len(sys.argv) > 1:
        # Command line mode
        path = sys.argv[1]
        try:
            analyze_path(path)
        except Exception as e:
            print(f"Error: {e}")
            print("Make sure to run as Administrator for low-level disk access.")
    else:
        # Interactive mode
        while True:
            try:
                path = input("Enter file or folder path (or 'quit' to exit): ").strip()
                if path.lower() in ['quit', 'exit', 'q']:
                    break
                if path:
                    if path.startswith('"') and path.endswith('"'):
                        path = path[1:-1]  # Remove quotes if present
                    try:
                        analyze_path(path)
                    except Exception as e:
                        print(f"Error: {e}")
                        print("Make sure to run as Administrator for low-level disk access.")
                    print()
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break

if __name__ == "__main__":
    main()