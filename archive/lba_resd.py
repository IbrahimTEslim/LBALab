import ctypes
from ctypes import wintypes
import os
import sys

# Constants
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = -1

# FSCTL constants
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064

# Structures
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
    """Get NTFS volume information including MFT location"""
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

def get_disk_geometry(drive_letter):
    """Get physical disk geometry for LBA calculations"""
    try:
        disk_path = r"\\.\PHYSICALDRIVE0"  # This might need adjustment for other drives
        handle = ctypes.windll.kernel32.CreateFileW(
            disk_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        
        if handle == INVALID_HANDLE_VALUE:
            # Fallback: assume standard 512 bytes per sector
            return 512
        
        try:
            geometry = DISK_GEOMETRY()
            returned = wintypes.DWORD()
            result = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                0x70000,  # IOCTL_DISK_GET_DRIVE_GEOMETRY
                None,
                0,
                ctypes.byref(geometry),
                ctypes.sizeof(geometry),
                ctypes.byref(returned),
                None
            )
            
            if result:
                return geometry.BytesPerSector
            else:
                return 512  # Default assumption
        finally:
            safe_handle_close(handle)
            
    except Exception:
        return 512  # Default sector size

def calculate_mft_record_lba(file_path, mft_record_number=None):
    """
    Calculate the LBA (Logical Block Address) of an MFT record.
    
    Args:
        file_path: Path to the file (to get its MFT record number if not provided)
        mft_record_number: Optional - specific MFT record number to calculate LBA for
    
    Returns:
        Dictionary with LBA information and calculation details
    """
    file_handle = None
    volume_handle = None
    
    try:
        # Get drive letter
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        if not drive_letter:
            raise NTFSError("Could not determine drive letter")
        
        # Get MFT record number if not provided
        if mft_record_number is None:
            if not os.path.exists(file_path):
                raise NTFSError(f"File does not exist: {file_path}")
            
            file_handle = open_file(file_path)
            file_info = BY_HANDLE_FILE_INFORMATION()
            if not ctypes.windll.kernel32.GetFileInformationByHandle(
                file_handle, ctypes.byref(file_info)
            ):
                raise ctypes.WinError()
            
            file_index = (file_info.nFileIndexHigh << 32) | file_info.nFileIndexLow
            mft_record_number = file_index & 0xFFFFFFFFFFFF
            sequence_number = (file_index >> 48) & 0xFFFF
            safe_handle_close(file_handle)
            file_handle = None
        else:
            sequence_number = 0  # Unknown when MFT record number is provided directly
        
        # Get volume information
        volume_handle = open_volume(drive_letter)
        vol_info = get_ntfs_volume_data(volume_handle)
        safe_handle_close(volume_handle)
        volume_handle = None
        
        # Get disk geometry for sector size
        physical_sector_size = get_disk_geometry(drive_letter)
        
        # Calculate MFT record location
        # MFT starts at: MftStartLcn * BytesPerCluster
        # Each MFT record is: BytesPerFileRecordSegment bytes
        # Record N is at: MFT_start + (N * record_size)
        
        mft_start_bytes = vol_info.MftStartLcn * vol_info.BytesPerCluster
        mft_record_offset_bytes = mft_record_number * vol_info.BytesPerFileRecordSegment
        mft_record_absolute_offset = mft_start_bytes + mft_record_offset_bytes
        
        # Convert to LBA (sectors)
        lba = mft_record_absolute_offset // physical_sector_size
        
        # Calculate additional useful information
        cluster_size = vol_info.BytesPerCluster
        sectors_per_cluster = cluster_size // physical_sector_size
        mft_start_lba = (vol_info.MftStartLcn * sectors_per_cluster)
        record_size_sectors = vol_info.BytesPerFileRecordSegment // physical_sector_size
        
        result = {
            "file_path": file_path,
            "mft_record_number": mft_record_number,
            "sequence_number": sequence_number,
            "lba": lba,
            "absolute_byte_offset": mft_record_absolute_offset,
            "mft_start_lcn": vol_info.MftStartLcn,
            "mft_start_lba": mft_start_lba,
            "bytes_per_sector": physical_sector_size,
            "bytes_per_cluster": cluster_size,
            "sectors_per_cluster": sectors_per_cluster,
            "mft_record_size": vol_info.BytesPerFileRecordSegment,
            "record_size_sectors": record_size_sectors,
            "drive_letter": drive_letter
        }
        
        return result
        
    except Exception as e:
        raise NTFSError(f"Error calculating MFT record LBA: {e}")
    finally:
        safe_handle_close(file_handle)
        safe_handle_close(volume_handle)

def print_lba_info(file_path, mft_record_number=None):
    """Print detailed LBA information for an MFT record"""
    try:
        info = calculate_mft_record_lba(file_path, mft_record_number)
        
        print(f"File: {info['file_path']}")
        print(f"Drive: {info['drive_letter']}:")
        print()
        
        print("=== MFT Record Information ===")
        print(f"MFT Record Number: {info['mft_record_number']}")
        if info['sequence_number'] > 0:
            print(f"Sequence Number: {info['sequence_number']}")
        print()
        
        print("=== Physical Location ===")
        print(f"LBA (Logical Block Address): {info['lba']:,}")
        print(f"Absolute Byte Offset: {info['absolute_byte_offset']:,}")
        print()
        
        print("=== Volume Layout ===")
        print(f"MFT Start LCN: {info['mft_start_lcn']:,}")
        print(f"MFT Start LBA: {info['mft_start_lba']:,}")
        print(f"Bytes per Sector: {info['bytes_per_sector']:,}")
        print(f"Bytes per Cluster: {info['bytes_per_cluster']:,}")
        print(f"Sectors per Cluster: {info['sectors_per_cluster']:,}")
        print(f"MFT Record Size: {info['mft_record_size']:,} bytes")
        print(f"MFT Record Size: {info['record_size_sectors']:,} sectors")
        print()
        
        print("=== Calculation Breakdown ===")
        print(f"1. MFT starts at LCN {info['mft_start_lcn']:,}")
        print(f"2. MFT byte offset = {info['mft_start_lcn']:,} × {info['bytes_per_cluster']:,} = {info['mft_start_lcn'] * info['bytes_per_cluster']:,}")
        print(f"3. Record {info['mft_record_number']:,} offset = {info['mft_record_number']:,} × {info['mft_record_size']:,} = {info['mft_record_number'] * info['mft_record_size']:,}")
        print(f"4. Total offset = {info['mft_start_lcn'] * info['bytes_per_cluster']:,} + {info['mft_record_number'] * info['mft_record_size']:,} = {info['absolute_byte_offset']:,}")
        print(f"5. LBA = {info['absolute_byte_offset']:,} ÷ {info['bytes_per_sector']:,} = {info['lba']:,}")
        
    except Exception as e:
        print(f"Error: {e}")

def get_file_mft_lba(file_path):
    """Get the LBA of a file's MFT record"""
    try:
        info = calculate_mft_record_lba(file_path)
        return info['lba']
    except Exception as e:
        raise NTFSError(f"Failed to get MFT LBA: {e}")

def bulk_mft_lba_calculator(file_paths):
    """Calculate LBA for multiple files"""
    results = []
    for file_path in file_paths:
        try:
            info = calculate_mft_record_lba(file_path)
            results.append({
                "file": file_path,
                "mft_record": info['mft_record_number'],
                "lba": info['lba'],
                "success": True
            })
        except Exception as e:
            results.append({
                "file": file_path,
                "error": str(e),
                "success": False
            })
    return results

# Example usage and testing
if __name__ == "__main__":
    print("NTFS MFT Record LBA Calculator")
    print("=" * 40)
    print("Calculates the physical disk LBA of MFT records")
    print("Requires Administrator privileges")
    print()
    
    if len(sys.argv) > 1:
        if sys.argv[1].isdigit():
            # MFT record number provided directly
            mft_record = int(sys.argv[1])
            drive = sys.argv[2] if len(sys.argv) > 2 else "C"
            dummy_path = f"{drive}:\\"
            print(f"Calculating LBA for MFT record {mft_record} on drive {drive}:")
            print_lba_info(dummy_path, mft_record)
        else:
            # File path provided
            file_path = sys.argv[1]
            print_lba_info(file_path)
    else:
        # Interactive mode
        while True:
            try:
                print("\nOptions:")
                print("1. Enter file path to get its MFT record LBA")
                print("2. Enter MFT record number directly")
                print("3. Quit")
                
                choice = input("\nChoose option (1-3): ").strip()
                
                if choice == "1":
                    path = input("Enter file path: ").strip()
                    if path:
                        print("\n" + "=" * 50)
                        print_lba_info(path)
                        
                elif choice == "2":
                    try:
                        mft_record = int(input("Enter MFT record number: ").strip())
                        drive = input("Enter drive letter (default C): ").strip() or "C"
                        dummy_path = f"{drive}:\\"
                        print("\n" + "=" * 50)
                        print_lba_info(dummy_path, mft_record)
                    except ValueError:
                        print("Invalid MFT record number")
                        
                elif choice == "3" or choice.lower() in ['quit', 'exit', 'q']:
                    break
                else:
                    print("Invalid option")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break

    # Test with some system files
    print("\n" + "=" * 60)
    print("Testing with system files:")
    test_files = [
        "C:\\Windows\\win.ini",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "C:\\$MFT"  # The MFT file itself
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n{'-' * 50}")
            print_lba_info(test_file)
        else:
            print(f"\nTest file not found: {test_file}")
    
    # Show some interesting MFT records
    print(f"\n{'-' * 50}")
    print("Special MFT Records:")
    special_records = [
        (0, "$MFT"),
        (1, "$MFTMirr"), 
        (2, "$LogFile"),
        (3, "$Volume"),
        (4, "$AttrDef"),
        (5, "Root Directory"),
        (6, "$Bitmap"),
        (7, "$Boot"),
        (8, "$BadClus"),
        (9, "$Secure"),
        (10, "$UpCase"),
        (11, "$Extend")
    ]
    
    try:
        for record_num, description in special_records[:3]:  # Just show first 3
            print(f"\n--- {description} (Record {record_num}) ---")
            print_lba_info("C:\\", record_num)
    except Exception as e:
        print(f"Note: Cannot access special MFT records - {e}")