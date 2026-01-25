import ctypes
import os
import struct
from ctypes import wintypes

# Windows constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_FLAG_NO_BUFFERING = 0x20000000

# Structures for partition info
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
    _fields_ = [("Mbr", MBR_PARTITION_INFO), ("Gpt", GPT_PARTITION_INFO)]

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

# API functions
kernel32 = ctypes.windll.kernel32
CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, 
                        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
CreateFileW.restype = wintypes.HANDLE

ReadFile = kernel32.ReadFile
ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, 
                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
ReadFile.restype = wintypes.BOOL

SetFilePointer = kernel32.SetFilePointer
CloseHandle = kernel32.CloseHandle

class IntegratedFileReader:
    def __init__(self):
        self.sector_size = 512
        
    def open_file(self, path):
        """Open file handle for retrieval pointer query"""
        path = r"\\?\\{}".format(os.path.abspath(path))
        handle = CreateFileW(path, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        if handle == -1:
            raise ctypes.WinError()
        return handle

    def open_drive(self, drive_path):
        """Open physical drive for raw sector reading"""
        handle = CreateFileW(
            drive_path, GENERIC_READ, 
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == -1:
            raise Exception(f"Failed to open drive {drive_path}. Error: {kernel32.GetLastError()}")
        return handle

    def get_file_extents(self, file_handle):
        """Get file's cluster locations"""
        input_buffer = STARTING_VCN_INPUT_BUFFER(0)
        out_size = 4096
        output_buffer = ctypes.create_string_buffer(out_size)
        returned = wintypes.DWORD()

        res = kernel32.DeviceIoControl(
            file_handle, FSCTL_GET_RETRIEVAL_POINTERS,
            ctypes.byref(input_buffer), ctypes.sizeof(input_buffer),
            output_buffer, out_size, ctypes.byref(returned), None
        )

        if not res:
            err = ctypes.GetLastError()
            if err == 1:  # ERROR_INVALID_FUNCTION - file is resident
                return None
            raise ctypes.WinError(err)

        # Parse extents
        if returned.value < 12:
            raise ValueError("Buffer too small for RETRIEVAL_POINTERS_BUFFER header")
        
        extent_count = int.from_bytes(output_buffer[0:4], 'little')
        starting_vcn = int.from_bytes(output_buffer[8:16], 'little')
        
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

    def get_partition_start_lba(self, drive_letter):
        """Get partition starting LBA"""
        volume_path = r"\\.\{}:".format(drive_letter)
        handle = CreateFileW(volume_path, 0, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)
        if handle == -1:
            raise ctypes.WinError()

        part_info = PARTITION_INFORMATION_EX()
        returned = wintypes.DWORD()
        
        try:
            res = kernel32.DeviceIoControl(
                handle, IOCTL_DISK_GET_PARTITION_INFO_EX,
                None, 0, ctypes.byref(part_info), ctypes.sizeof(part_info),
                ctypes.byref(returned), None
            )
            if not res:
                raise ctypes.WinError()
        finally:
            CloseHandle(handle)

        starting_lba = part_info.StartingOffset // self.sector_size
        return starting_lba

    def get_sectors_per_cluster(self, drive_letter):
        """Get cluster size in sectors"""
        sectors_per_cluster = wintypes.DWORD()
        bytes_per_sector = wintypes.DWORD()
        free_clusters = wintypes.DWORD()
        total_clusters = wintypes.DWORD()

        res = kernel32.GetDiskFreeSpaceW(
            ctypes.c_wchar_p(drive_letter + ":\\"),
            ctypes.byref(sectors_per_cluster), ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters), ctypes.byref(total_clusters)
        )
        if not res:
            raise ctypes.WinError()

        return sectors_per_cluster.value, bytes_per_sector.value

    def read_raw_sectors(self, drive_handle, lba, sector_count=1):
        """Read raw sectors from drive"""
        size = sector_count * self.sector_size
        byte_offset = lba * self.sector_size
        
        # Set file pointer
        low_part = byte_offset & 0xFFFFFFFF
        high_part = (byte_offset >> 32) & 0xFFFFFFFF
        high_part_ptr = ctypes.pointer(wintypes.LONG(high_part))
        
        result = SetFilePointer(drive_handle, low_part, high_part_ptr, 0)
        if result == 0xFFFFFFFF:
            error = kernel32.GetLastError()
            if error != 0:
                raise Exception(f"Failed to set file pointer. Error: {error}")
        
        # Read data
        buffer = ctypes.create_string_buffer(size)
        bytes_read = wintypes.DWORD(0)
        
        success = ReadFile(drive_handle, buffer, size, ctypes.byref(bytes_read), None)
        if not success:
            raise Exception(f"Failed to read data. Error: {kernel32.GetLastError()}")
        
        return buffer.raw[:bytes_read.value]

    def get_physical_drive_number(self, drive_letter):
        """Simple mapping of drive letter to physical drive number"""
        # This is a simplified version - in practice, you might need more robust detection
        drive_char = drive_letter.upper()
        if drive_char == 'C':
            return 0
        else:
            return ord(drive_char) - ord('C')

    def read_file_content_from_disk(self, file_path):
        """
        Read file content directly from disk using cluster mapping
        
        Args:
            file_path: Path to the file
            
        Returns:
            dict: File analysis with actual disk content vs logical file content
        """
        if not os.path.exists(file_path):
            return {'error': 'File does not exist'}
        
        # Get file info
        file_size = os.path.getsize(file_path)
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        
        result = {
            'file_path': file_path,
            'file_size': file_size,
            'drive_letter': drive_letter,
            'logical_content': None,
            'disk_content': None,
            'extents': None,
            'is_resident': False,
            'content_match': False
        }
        
        try:
            # Read logical file content
            with open(file_path, 'rb') as f:
                result['logical_content'] = f.read()
            
            # Get disk geometry
            partition_start_lba = self.get_partition_start_lba(drive_letter)
            sectors_per_cluster, bytes_per_sector = self.get_sectors_per_cluster(drive_letter)
            cluster_size = sectors_per_cluster * bytes_per_sector
            
            result['partition_start_lba'] = partition_start_lba
            result['sectors_per_cluster'] = sectors_per_cluster
            result['bytes_per_sector'] = bytes_per_sector
            result['cluster_size'] = cluster_size
            
            # Get file extents
            file_handle = self.open_file(file_path)
            try:
                extents = self.get_file_extents(file_handle)
                result['extents'] = extents
                
                if extents is None:
                    result['is_resident'] = True
                    result['disk_content'] = b'<FILE IS RESIDENT IN MFT>'
                else:
                    # Read actual disk content from extents
                    physical_drive_num = self.get_physical_drive_number(drive_letter)
                    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
                    
                    disk_handle = self.open_drive(drive_path)
                    try:
                        disk_content = b''
                        
                        for start_vcn, next_vcn, lcn in extents:
                            if lcn == -1:  # Sparse extent
                                cluster_count = next_vcn - start_vcn
                                disk_content += b'\x00' * (cluster_count * cluster_size)
                            else:
                                # Calculate actual LBA
                                lba = partition_start_lba + (lcn * sectors_per_cluster)
                                cluster_count = next_vcn - start_vcn
                                total_sectors = cluster_count * sectors_per_cluster
                                
                                # Read the clusters
                                cluster_data = self.read_raw_sectors(disk_handle, lba, total_sectors)
                                disk_content += cluster_data
                        
                        # Trim to actual file size
                        result['disk_content'] = disk_content[:file_size]
                        
                    finally:
                        CloseHandle(disk_handle)
                        
            finally:
                CloseHandle(file_handle)
            
            # Compare contents
            if result['logical_content'] and result['disk_content']:
                if isinstance(result['disk_content'], bytes):
                    result['content_match'] = result['logical_content'] == result['disk_content']
                else:
                    result['content_match'] = False
            
        except Exception as e:
            result['error'] = str(e)
            import traceback
            result['traceback'] = traceback.format_exc()
        
        return result

    def analyze_content_differences(self, result):
        """Analyze why logical and disk content might differ"""
        if 'error' in result:
            return {'analysis': 'Error occurred during reading'}
        
        analysis = {'reasons': []}
        
        if result['is_resident']:
            analysis['reasons'].append("File is resident (stored in MFT record)")
            return analysis
        
        if not result['logical_content'] or not isinstance(result['disk_content'], bytes):
            analysis['reasons'].append("Could not read one or both content sources")
            return analysis
        
        logical_size = len(result['logical_content'])
        disk_size = len(result['disk_content'])
        
        if logical_size != disk_size:
            analysis['reasons'].append(f"Size mismatch: logical={logical_size}, disk={disk_size}")
        
        if result['content_match']:
            analysis['reasons'].append("Contents match perfectly!")
        else:
            # Find first difference
            min_size = min(logical_size, disk_size)
            first_diff = -1
            for i in range(min_size):
                if result['logical_content'][i] != result['disk_content'][i]:
                    first_diff = i
                    break
            
            if first_diff >= 0:
                analysis['reasons'].append(f"First difference at byte {first_diff}")
                analysis['logical_byte'] = result['logical_content'][first_diff]
                analysis['disk_byte'] = result['disk_content'][first_diff]
            
            # Check if it's just padding
            if logical_size < disk_size:
                padding = result['disk_content'][logical_size:]
                if all(b == 0 for b in padding):
                    analysis['reasons'].append("Disk content has null padding after file data")
                else:
                    analysis['reasons'].append("Disk content has non-null data after file end")
        
        return analysis

    def hex_dump(self, data, offset=0, length=None):
        """Create hex dump of data"""
        if length is None:
            length = min(len(data), 256)  # Limit to first 256 bytes by default
        
        lines = []
        for i in range(0, length, 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{offset+i:08x}: {hex_part:<48} {ascii_part}")
        
        return '\n'.join(lines)


def main():
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    if not is_admin():
        print("This script requires administrator privileges!")
        print("Run as administrator to access physical drives.")
        return
    
    reader = IntegratedFileReader()
    
    # Get file path from user
    file_path = input("Enter file path to analyze: ").strip('"')
    
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        return
    
    print(f"\nAnalyzing file: {file_path}")
    print("=" * 60)
    
    # Read and compare content
    result = reader.read_file_content_from_disk(file_path)
    
    if 'error' in result:
        print(f"Error: {result['error']}")
        if 'traceback' in result:
            print("Traceback:")
            print(result['traceback'])
        return
    
    # Print basic info
    print(f"File size: {result['file_size']:,} bytes")
    print(f"Drive: {result['drive_letter']}: (PhysicalDrive{reader.get_physical_drive_number(result['drive_letter'])})")
    print(f"Partition start LBA: {result['partition_start_lba']}")
    print(f"Sectors per cluster: {result['sectors_per_cluster']}")
    print(f"Cluster size: {result['cluster_size']} bytes")
    
    # Print extent information
    if result['is_resident']:
        print("\nFile is RESIDENT (stored in MFT record)")
    else:
        print(f"\nFile extents:")
        for i, (start_vcn, next_vcn, lcn) in enumerate(result['extents']):
            cluster_count = next_vcn - start_vcn
            if lcn == -1:
                print(f"  Extent {i+1}: VCN {start_vcn}-{next_vcn-1} ({cluster_count} clusters) : SPARSE")
            else:
                lba = result['partition_start_lba'] + (lcn * result['sectors_per_cluster'])
                size_bytes = cluster_count * result['cluster_size']
                print(f"  Extent {i+1}: VCN {start_vcn}-{next_vcn-1} ({cluster_count} clusters, {size_bytes} bytes)")
                print(f"             LCN {lcn} : LBA {lba}")
    
    # Analyze differences
    analysis = reader.analyze_content_differences(result)
    print(f"\nContent Analysis:")
    print(f"Contents match: {result['content_match']}")
    
    for reason in analysis['reasons']:
        print(f"  - {reason}")
    
    if 'logical_byte' in analysis:
        print(f"  Logical byte at diff: 0x{analysis['logical_byte']:02x}")
        print(f"  Disk byte at diff: 0x{analysis['disk_byte']:02x}")
    
    # Show hex dumps
    if result['logical_content']:
        print(f"\nLogical file content (first 128 bytes):")
        print(reader.hex_dump(result['logical_content'], 0, 128))
    
    if isinstance(result['disk_content'], bytes):
        print(f"\nDisk content (first 128 bytes):")
        print(reader.hex_dump(result['disk_content'], 0, 128))
    else:
        print(f"\nDisk content: {result['disk_content']}")


if __name__ == "__main__":
    main()