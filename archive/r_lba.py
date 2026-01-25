import os
import ctypes
from ctypes import wintypes
import struct
import subprocess
import tempfile

# Windows API constants
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000

# Import Windows API functions
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
SetFilePointer.argtypes = [wintypes.HANDLE, wintypes.LONG, ctypes.POINTER(wintypes.LONG), wintypes.DWORD]
SetFilePointer.restype = wintypes.DWORD

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

class NTFSStructures:
    """NTFS structure definitions"""
    
    # MFT Record header structure
    MFT_RECORD_HEADER_FORMAT = '<4sHHQLLLLLHH'
    MFT_RECORD_HEADER_SIZE = 42
    
    # Attribute header structure
    ATTR_HEADER_FORMAT = '<LLBBHH'
    ATTR_HEADER_SIZE = 16
    
    # Non-resident attribute header
    NON_RESIDENT_ATTR_FORMAT = '<QQHHQQQQ'
    NON_RESIDENT_ATTR_SIZE = 48
    
    # Resident attribute header
    RESIDENT_ATTR_FORMAT = '<LHH'
    RESIDENT_ATTR_SIZE = 8
    
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
    ATTR_END_OF_ATTRIBUTES = 0xFFFFFFFF

class LBAReader:
    def __init__(self, drive_path, sector_size=512, mft_record_size=1024):
        """
        Initialize LBA reader for a specific drive
        
        Args:
            drive_path: Physical drive path (e.g., r"\\.\PhysicalDrive0")
            sector_size: Size of each sector in bytes (typically 512 or 4096)
            mft_record_size: Size of MFT record in bytes (typically 1024)
        """
        self.drive_path = drive_path
        self.sector_size = sector_size
        self.mft_record_size = mft_record_size
        self.handle = None
    
    def open_drive(self):
        """Open the drive for direct access"""
        self.handle = CreateFileW(
            self.drive_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_NO_BUFFERING,
            None
        )
        
        if self.handle == -1:  # INVALID_HANDLE_VALUE
            raise Exception(f"Failed to open drive {self.drive_path}. Error: {kernel32.GetLastError()}")
    
    def close_drive(self):
        """Close the drive handle"""
        if self.handle and self.handle != -1:
            CloseHandle(self.handle)
            self.handle = None
    
    def read_lba(self, lba, size=None):
        """
        Read data from a specific LBA
        
        Args:
            lba: Logical Block Address (sector number)
            size: Number of bytes to read (defaults to sector_size)
        
        Returns:
            bytes: Data read from the LBA
        """
        if not self.handle or self.handle == -1:
            raise Exception("Drive not opened. Call open_drive() first.")
        
        if size is None:
            size = self.sector_size
        
        # Ensure size is aligned to sector boundary
        aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
        
        # Calculate byte offset from LBA
        byte_offset = lba * self.sector_size
        
        # Set file pointer to the LBA position
        low_part = byte_offset & 0xFFFFFFFF
        high_part = (byte_offset >> 32) & 0xFFFFFFFF
        high_part_ptr = ctypes.pointer(wintypes.LONG(high_part))
        
        result = SetFilePointer(self.handle, low_part, high_part_ptr, 0)  # FILE_BEGIN = 0
        if result == 0xFFFFFFFF:  # INVALID_SET_FILE_POINTER
            error = kernel32.GetLastError()
            if error != 0:  # NO_ERROR
                raise Exception(f"Failed to set file pointer. Error: {error}")
        
        # Read the data
        buffer = ctypes.create_string_buffer(aligned_size)
        bytes_read = wintypes.DWORD(0)
        
        success = ReadFile(
            self.handle,
            buffer,
            aligned_size,
            ctypes.byref(bytes_read),
            None
        )
        
        if not success:
            raise Exception(f"Failed to read data. Error: {kernel32.GetLastError()}")
        
        # Return only the requested amount
        return buffer.raw[:size]
    
    def is_mft_record(self, data):
        """
        Check if the data looks like an MFT record
        
        Args:
            data: Raw bytes data
            
        Returns:
            bool: True if it appears to be an MFT record
        """
        if len(data) < NTFSStructures.MFT_RECORD_HEADER_SIZE:
            return False
        
        # Check MFT record signature
        signature = data[:4]
        return signature in [b'FILE', b'BAAD']
    
    def parse_mft_record(self, data):
        """
        Parse MFT record and extract attributes
        
        Args:
            data: Raw MFT record data
            
        Returns:
            dict: Parsed MFT record information
        """
        if len(data) < NTFSStructures.MFT_RECORD_HEADER_SIZE:
            raise ValueError("Data too small to be an MFT record")
        
        # Parse MFT record header
        header_data = struct.unpack(
            NTFSStructures.MFT_RECORD_HEADER_FORMAT,
            data[:NTFSStructures.MFT_RECORD_HEADER_SIZE]
        )
        
        record_info = {
            'signature': header_data[0].decode('ascii', errors='ignore'),
            'usa_offset': header_data[1],
            'usa_count': header_data[2],
            'lsn': header_data[3],
            'sequence': header_data[4],
            'link_count': header_data[5],
            'attr_offset': header_data[6],
            'flags': header_data[7],
            'bytes_in_use': header_data[8],
            'bytes_allocated': header_data[9],
            'base_file_reference': header_data[10],
            'next_attr_instance': header_data[11],
            'attributes': []
        }
        
        # Parse attributes
        offset = record_info['attr_offset']
        
        while offset < len(data) and offset < record_info['bytes_in_use']:
            if offset + NTFSStructures.ATTR_HEADER_SIZE > len(data):
                break
            
            attr_header = struct.unpack(
                NTFSStructures.ATTR_HEADER_FORMAT,
                data[offset:offset + NTFSStructures.ATTR_HEADER_SIZE]
            )
            
            attr_type = attr_header[0]
            attr_length = attr_header[1]
            non_resident = attr_header[2]
            name_length = attr_header[3]
            name_offset = attr_header[4]
            flags = attr_header[5]
            
            # End of attributes marker
            if attr_type == NTFSStructures.ATTR_END_OF_ATTRIBUTES:
                break
            
            attr_info = {
                'type': attr_type,
                'type_name': self.get_attr_type_name(attr_type),
                'length': attr_length,
                'non_resident': bool(non_resident),
                'name_length': name_length,
                'name_offset': name_offset,
                'flags': flags,
                'offset': offset
            }
            
            # Parse attribute name if present
            if name_length > 0:
                name_start = offset + name_offset
                name_end = name_start + (name_length * 2)  # Unicode name
                if name_end <= len(data):
                    attr_info['name'] = data[name_start:name_end].decode('utf-16le', errors='ignore')
            
            # Parse attribute data
            if not non_resident:
                # Resident attribute
                if offset + NTFSStructures.ATTR_HEADER_SIZE + NTFSStructures.RESIDENT_ATTR_SIZE <= len(data):
                    resident_header = struct.unpack(
                        NTFSStructures.RESIDENT_ATTR_FORMAT,
                        data[offset + NTFSStructures.ATTR_HEADER_SIZE:
                             offset + NTFSStructures.ATTR_HEADER_SIZE + NTFSStructures.RESIDENT_ATTR_SIZE]
                    )
                    
                    attr_info['value_length'] = resident_header[0]
                    attr_info['value_offset'] = resident_header[1]
                    
                    # Extract the actual data
                    value_start = offset + resident_header[1]
                    value_end = value_start + resident_header[0]
                    if value_end <= len(data):
                        attr_info['data'] = data[value_start:value_end]
            else:
                # Non-resident attribute
                if offset + NTFSStructures.ATTR_HEADER_SIZE + NTFSStructures.NON_RESIDENT_ATTR_SIZE <= len(data):
                    nonres_header = struct.unpack(
                        NTFSStructures.NON_RESIDENT_ATTR_FORMAT,
                        data[offset + NTFSStructures.ATTR_HEADER_SIZE:
                             offset + NTFSStructures.ATTR_HEADER_SIZE + NTFSStructures.NON_RESIDENT_ATTR_SIZE]
                    )
                    
                    attr_info['start_vcn'] = nonres_header[0]
                    attr_info['last_vcn'] = nonres_header[1]
                    attr_info['datarun_offset'] = nonres_header[2]
                    attr_info['compression_unit'] = nonres_header[3]
                    attr_info['allocated_size'] = nonres_header[4]
                    attr_info['data_size'] = nonres_header[5]
                    attr_info['initialized_size'] = nonres_header[6]
                    attr_info['compressed_size'] = nonres_header[7]
                    
                    # Extract data run information
                    datarun_start = offset + attr_info['datarun_offset']
                    if datarun_start < len(data):
                        attr_info['data_runs'] = self.parse_data_runs(data[datarun_start:offset + attr_length])
            
            record_info['attributes'].append(attr_info)
            
            # Move to next attribute
            if attr_length == 0:
                break
            offset += attr_length
        
        return record_info
    
    def get_attr_type_name(self, attr_type):
        """Get human-readable attribute type name"""
        attr_names = {
            0x10: '$STANDARD_INFORMATION',
            0x20: '$ATTRIBUTE_LIST',
            0x30: '$FILE_NAME',
            0x40: '$OBJECT_ID',
            0x50: '$SECURITY_DESCRIPTOR',
            0x60: '$VOLUME_NAME',
            0x70: '$VOLUME_INFORMATION',
            0x80: '$DATA',
            0x90: '$INDEX_ROOT',
            0xA0: '$INDEX_ALLOCATION',
            0xB0: '$BITMAP',
            0xC0: '$REPARSE_POINT',
            0xD0: '$EA_INFORMATION',
            0xE0: '$EA',
            0xF0: '$PROPERTY_SET',
            0x100: '$LOGGED_UTILITY_STREAM'
        }
        return attr_names.get(attr_type, f'UNKNOWN_{attr_type:X}')
    
    def parse_data_runs(self, data):
        """
        Parse NTFS data runs (cluster run-length encoding)
        
        Args:
            data: Raw data run bytes
            
        Returns:
            list: List of (cluster, length) tuples
        """
        data_runs = []
        offset = 0
        current_cluster = 0
        
        while offset < len(data) and data[offset] != 0:
            if offset >= len(data):
                break
                
            header = data[offset]
            if header == 0:
                break
            
            length_size = header & 0x0F
            cluster_size = (header & 0xF0) >> 4
            
            if length_size == 0 or cluster_size == 0:
                break
            
            offset += 1
            
            # Read length
            if offset + length_size > len(data):
                break
            length = int.from_bytes(data[offset:offset + length_size], 'little')
            offset += length_size
            
            # Read cluster offset
            if offset + cluster_size > len(data):
                break
            cluster_offset = int.from_bytes(data[offset:offset + cluster_size], 'little', signed=True)
            offset += cluster_size
            
            current_cluster += cluster_offset
            data_runs.append((current_cluster, length))
        
        return data_runs
    
    def extract_data_attribute(self, mft_record):
        """
        Extract $DATA attribute information from MFT record
        
        Args:
            mft_record: Parsed MFT record dictionary
            
        Returns:
            dict: $DATA attribute information
        """
        data_attributes = []
        
        for attr in mft_record['attributes']:
            if attr['type'] == NTFSStructures.ATTR_DATA:
                data_attributes.append(attr)
        
        return data_attributes
    
    def read_lba_content(self, lba, max_size=None):
        """
        Read LBA content and determine if it's MFT record or file data
        
        Args:
            lba: Logical Block Address
            max_size: Maximum size to read (None for auto-detection)
            
        Returns:
            dict: Analysis results with content and type information
        """
        # First read one sector to analyze
        initial_data = self.read_lba(lba, self.sector_size)
        
        result = {
            'lba': lba,
            'is_mft_record': False,
            'content_type': 'unknown',
            'data': initial_data,
            'analysis': {}
        }
        
        # Check if it's an MFT record
        if self.is_mft_record(initial_data):
            result['is_mft_record'] = True
            result['content_type'] = 'mft_record'
            
            # Read full MFT record
            mft_data = self.read_lba(lba, self.mft_record_size)
            result['data'] = mft_data
            
            try:
                # Parse MFT record
                mft_record = self.parse_mft_record(mft_data)
                result['analysis'] = mft_record
                
                # Extract $DATA attributes
                data_attrs = self.extract_data_attribute(mft_record)
                result['data_attributes'] = data_attrs
                
                if data_attrs:
                    result['content_type'] = 'mft_record_with_data'
                    
            except Exception as e:
                result['parse_error'] = str(e)
        else:
            # Assume it's file content
            result['content_type'] = 'file_data'
            
            # If max_size specified, read more data
            if max_size and max_size > self.sector_size:
                try:
                    full_data = self.read_lba(lba, max_size)
                    result['data'] = full_data
                except Exception as e:
                    result['read_error'] = str(e)
            
            # Try to detect file type
            result['analysis'] = self.analyze_file_data(result['data'])
        
        return result
    
    def analyze_file_data(self, data):
        """
        Analyze raw file data to determine file type and characteristics
        
        Args:
            data: Raw file data bytes
            
        Returns:
            dict: Analysis results
        """
        analysis = {
            'size': len(data),
            'file_type': 'unknown',
            'is_text': False,
            'encoding': None
        }
        
        if len(data) == 0:
            analysis['file_type'] = 'empty'
            return analysis
        
        # Check common file signatures
        signatures = {
            b'\x4D\x5A': 'PE executable',
            b'\x50\x4B\x03\x04': 'ZIP archive',
            b'\x50\x4B\x05\x06': 'ZIP archive (empty)',
            b'\x50\x4B\x07\x08': 'ZIP archive (spanned)',
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
        
        # Check if it's text data
        try:
            # Try UTF-8
            text = data.decode('utf-8')
            analysis['is_text'] = True
            analysis['encoding'] = 'utf-8'
            analysis['text_preview'] = text[:200] + ('...' if len(text) > 200 else '')
        except UnicodeDecodeError:
            try:
                # Try UTF-16
                text = data.decode('utf-16le')
                analysis['is_text'] = True
                analysis['encoding'] = 'utf-16le'
                analysis['text_preview'] = text[:200] + ('...' if len(text) > 200 else '')
            except UnicodeDecodeError:
                # Check if it's mostly ASCII
                ascii_chars = sum(1 for b in data[:1000] if 32 <= b <= 126 or b in [9, 10, 13])
                if ascii_chars / min(len(data), 1000) > 0.7:
                    analysis['is_text'] = True
                    analysis['encoding'] = 'ascii-like'
                    try:
                        analysis['text_preview'] = data.decode('ascii', errors='ignore')[:200]
                    except:
                        pass
        
        return analysis
    
    def __enter__(self):
        """Context manager entry"""
        self.open_drive()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_drive()


def get_physical_drive_from_path(file_path):
    """Get physical drive number from file path (simplified version)"""
    drive_letter = os.path.splitdrive(os.path.abspath(file_path))[0]
    if not drive_letter.endswith(':'):
        drive_letter += ':'
    
    # Simple heuristic (for more robust version, use the previous implementation)
    drive_char = drive_letter.upper().replace(':', '')
    if drive_char == 'C':
        return 0
    else:
        return ord(drive_char) - ord('C')


def read_lba_from_path(file_path, lba, max_size=None):
    """
    Read LBA content from drive containing the specified file path
    
    Args:
        file_path: File path to determine which drive to read from
        lba: Logical Block Address
        max_size: Maximum size to read for file data
        
    Returns:
        dict: Analysis results
    """
    try:
        physical_drive_num = get_physical_drive_from_path(file_path)
        drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
        
        print(f"Reading LBA {lba} from {drive_path} (derived from {file_path})")
        
        with LBAReader(drive_path) as reader:
            return reader.read_lba_content(lba, max_size)
            
    except Exception as e:
        return {
            'error': str(e),
            'lba': lba,
            'file_path': file_path
        }


def print_mft_data_attributes(data_attributes):
    """Pretty print $DATA attributes from MFT record"""
    if not data_attributes:
        print("No $DATA attributes found")
        return
    
    for i, attr in enumerate(data_attributes):
        print(f"\n--- $DATA Attribute {i + 1} ---")
        print(f"Type: {attr['type_name']}")
        print(f"Non-resident: {attr['non_resident']}")
        
        if 'name' in attr:
            print(f"Name: {attr['name']}")
        
        if attr['non_resident']:
            print(f"Allocated size: {attr.get('allocated_size', 0):,} bytes")
            print(f"Data size: {attr.get('data_size', 0):,} bytes")
            print(f"Initialized size: {attr.get('initialized_size', 0):,} bytes")
            
            if 'data_runs' in attr:
                print("Data runs:")
                for j, (cluster, length) in enumerate(attr['data_runs']):
                    print(f"  Run {j + 1}: Cluster {cluster}, Length {length}")
        else:
            if 'data' in attr:
                print(f"Data size: {len(attr['data'])} bytes")
                if len(attr['data']) <= 64:
                    print(f"Data (hex): {attr['data'].hex()}")
                else:
                    print(f"Data preview (hex): {attr['data'][:32].hex()}...")


# Example usage and testing
if __name__ == "__main__":
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    if not is_admin():
        print("This script requires administrator privileges!")
        print("Run as administrator to access physical drives.")
        exit(1)
    
    # Example 1: Read a specific LBA and analyze
    print("=== LBA Content Reader ===")
    
    # Test with different LBAs
    test_cases = [
        {"file_path": "C:\\", "lba": 935218376, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459073, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459074, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459075, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459076, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459077, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459078, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459079, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\", "lba": 8459080, "description": "Boot sector (MBR)"},
        # {"file_path": "C:\\Windows\\System32", "lba": 786432, "description": "Potential MFT area"},
        # {"file_path": "C:\\Windows\\System32", "lba": 1000, "description": "Random data area"}
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing {test_case['description']} ---")
        print(f"LBA: {test_case['lba']}")
        
        try:
            result = read_lba_from_path(
                test_case["file_path"], 
                test_case["lba"], 
                max_size=4096  # Read up to 4KB for file data
            )
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                continue
            
            print(f"Content type: {result['content_type']}")
            print(f"Is MFT record: {result['is_mft_record']}")
            print(f"Data size: {len(result['data'])} bytes")
            
            if result['is_mft_record']:
                print("\n--- MFT Record Analysis ---")
                if 'analysis' in result:
                    mft = result['analysis']
                    print(f"Signature: {mft.get('signature', 'Unknown')}")
                    print(f"Sequence: {mft.get('sequence', 0)}")
                    print(f"Link count: {mft.get('link_count', 0)}")
                    print(f"Bytes in use: {mft.get('bytes_in_use', 0)}")
                    print(f"Attributes count: {len(mft.get('attributes', []))}")
                    
                    if 'data_attributes' in result:
                        print_mft_data_attributes(result['data_attributes'])
                
                if 'parse_error' in result:
                    print(f"Parse error: {result['parse_error']}")
            
            else:
                print("\n--- File Data Analysis ---")
                analysis = result['analysis']
                print(f"Detected file type: {analysis['file_type']}")
                print(f"Is text: {analysis['is_text']}")
                
                if analysis['is_text']:
                    print(f"Encoding: {analysis.get('encoding', 'unknown')}")
                    if 'text_preview' in analysis:
                        print(f"Text preview: {repr(analysis['text_preview'])}")
                
                # Show hex dump of first 128 bytes
                print(f"\nHex dump (first 128 bytes):")
                hex_data = result['data'][:128]
                for i in range(0, len(hex_data), 16):
                    hex_line = ' '.join(f'{b:02x}' for b in hex_data[i:i+16])
                    ascii_line = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in hex_data[i:i+16])
                    print(f"{i:08x}: {hex_line:<48} {ascii_line}")
        
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== Manual LBA Testing ===")
    print("You can now test specific LBAs:")
    print("result = read_lba_from_path('C:\\\\', 12345, max_size=8192)")