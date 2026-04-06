#!/usr/bin/env python3
"""
Comprehensive Analyzer - Complete file analysis with detailed output
Contains print_file_analysis() and analyze_file_complete()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI
from modules import FileAnalyzer, ExtentMapper, MFTParser, LBAReader

class ComprehensiveAnalyzer:
    """Complete file analysis with all details"""
    
    def __init__(self):
        self.file_analyzer = FileAnalyzer()
        self.extent_mapper = ExtentMapper()
        self.mft_parser = MFTParser()
        self.lba_reader = LBAReader()
        self.disk_io = DiskIO()
    
    def analyze_file_complete(self, file_path):
        """Complete analysis returning structured data"""
        if not os.path.exists(file_path):
            raise ValueError(f"File does not exist: {file_path}")
        
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "").upper()
        if not drive_letter:
            raise ValueError("Could not determine drive letter")
        
        # Get all info
        file_info = self.file_analyzer.get_file_info(file_path)
        vol_info = self.file_analyzer.get_volume_info(drive_letter)
        partition_lba = self.file_analyzer.get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = self.file_analyzer.get_sectors_per_cluster(drive_letter)
        
        # Calculate MFT record LBA
        mft_start_bytes = vol_info['mft_start_lcn'] * vol_info['bytes_per_cluster']
        mft_record_offset = file_info['mft_record_number'] * vol_info['mft_record_size']
        mft_absolute_offset = mft_start_bytes + mft_record_offset
        mft_lba_rel = mft_absolute_offset // 512
        mft_lba_abs = partition_lba + mft_lba_rel
        
        result = {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "is_directory": os.path.isdir(file_path),
            "drive_letter": drive_letter,
            "file_info": file_info,
            "volume_info": {
                "partition_start_lba": partition_lba,
                "bytes_per_sector": bytes_per_sector,
                "bytes_per_cluster": vol_info['bytes_per_cluster'],
                "sectors_per_cluster": sectors_per_cluster,
                "mft_start_lcn": vol_info['mft_start_lcn'],
                "mft_record_size": vol_info['mft_record_size']
            },
            "mft_record_lba": {
                "relative": mft_lba_rel,
                "absolute": mft_lba_abs,
                "byte_offset": mft_absolute_offset
            },
            "is_resident": None,
            "extents": None,
            "data_attributes": None
        }
        
        # Get extents if file
        if not os.path.isdir(file_path):
            try:
                extent_data = self.extent_mapper.map_extents_to_lba(file_path)
                result["is_resident"] = extent_data['is_resident']
                result["extents"] = extent_data['extents']
            except:
                pass
        
        return result
    
    def print_file_analysis(self, file_path):
        """Print comprehensive file analysis - THE MAIN FUNCTION"""
        if not os.path.exists(file_path):
            print(f"Path does not exist: {file_path}")
            return
        
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "").upper()
        
        # Get all info
        vol_info = self.file_analyzer.get_volume_info(drive_letter)
        partition_lba = self.file_analyzer.get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = self.file_analyzer.get_sectors_per_cluster(drive_letter)
        file_info = self.file_analyzer.get_file_info(file_path)
        is_directory = os.path.isdir(file_path)
        file_size = 0 if is_directory else os.path.getsize(file_path)
        
        # Calculate MFT LBA
        mft_start_bytes = vol_info['mft_start_lcn'] * vol_info['bytes_per_cluster']
        mft_record_offset = file_info['mft_record_number'] * vol_info['mft_record_size']
        mft_absolute_offset = mft_start_bytes + mft_record_offset
        mft_lba_rel = mft_absolute_offset // bytes_per_sector
        mft_lba_abs = partition_lba + mft_lba_rel
        
        # Print analysis
        print("=" * 80)
        print(f"NTFS Analysis for: {file_path}")
        print("=" * 80)
        print(f"Type: {'Directory' if is_directory else 'File'}")
        if not is_directory:
            print(f"Size: {file_size:,} bytes")
        print(f"Drive: {drive_letter}:")
        print()
        
        print("=== MFT Record Information ===")
        print(f"MFT Record Number: {file_info['mft_record_number']:,}")
        print(f"Sequence Number: {file_info['sequence_number']}")
        print(f"MFT Record LBA (relative): {mft_lba_rel:,}")
        print(f"MFT Record LBA (absolute): {mft_lba_abs:,}")
        print(f"MFT Record Byte Offset: {mft_absolute_offset:,}")
        print()
        
        print("=== Volume Information ===")
        print(f"Partition Start LBA: {partition_lba:,}")
        print(f"Bytes per Sector: {bytes_per_sector:,}")
        print(f"Bytes per Cluster: {vol_info['bytes_per_cluster']:,}")
        print(f"Sectors per Cluster: {sectors_per_cluster:,}")
        print(f"MFT Start LCN: {vol_info['mft_start_lcn']:,}")
        print(f"MFT Record Size: {vol_info['mft_record_size']:,} bytes")
        print()
        
        # For files, show extents
        if not is_directory:
            try:
                extent_data = self.extent_mapper.map_extents_to_lba(file_path)
                
                if extent_data['is_resident']:
                    print("=== File Data Status ===")
                    print("Status: RESIDENT (file data stored inside MFT record)")
                else:
                    print("=== File Data Status ===")
                    print("Status: NON-RESIDENT (file data stored in clusters on disk)")
                    print()
                    print("=== File Data Extents (VCN   LCN   LBA) ===")
                    
                    for i, ext in enumerate(extent_data['extents'], 1):
                        if ext['type'] == 'sparse':
                            print(f"Extent {i}: VCN {ext['start_vcn']}-{ext['next_vcn']-1} ({ext['cluster_count']} clusters)   SPARSE")
                        else:
                            print(f"Extent {i}: VCN {ext['start_vcn']}-{ext['next_vcn']-1} ({ext['cluster_count']} clusters, {ext['size_bytes']:,} bytes)")
                            print(f"             LCN {ext['lcn']:,}   LBA {ext['lba_absolute']:,}   Byte offset {ext['byte_offset']:,}")
                            
                            # Content verification for first extent
                            if i == 1:
                                try:
                                    drive_num = self.disk_io.get_physical_drive_number(drive_letter)
                                    print(f"           Volume {drive_letter}: is on PhysicalDrive{drive_num}")
                                    
                                    # Read from both sources
                                    content_phys = self.lba_reader.read_physical(drive_num, ext['lba_absolute'], 512)
                                    content_vol = self.lba_reader.read_volume(drive_letter, ext['lba_relative'], 512)
                                    
                                    with open(file_path, 'rb') as f:
                                        file_content = f.read(512)
                                    
                                    print(f"           PhysicalDrive{drive_num}[{ext['lba_absolute']}]: {content_phys[:32].hex()}")
                                    print(f"           Volume {drive_letter}:[{ext['lba_relative']}]:       {content_vol[:32].hex()}")
                                    print(f"           File API:                {file_content[:32].hex()}")
                                    print(f"           PhysDrive Match: {' YES' if content_phys[:32] == file_content[:32] else ' NO'}")
                                    print(f"           Volume Match:    {' YES' if content_vol[:32] == file_content[:32] else ' NO'}")
                                except Exception as e:
                                    print(f"           Content verification failed: {e}")
            except Exception as e:
                print(f"Error analyzing extents: {e}")
        
        print()
        print("=== MFT Record LBA Calculation ===")
        print(f"1. MFT starts at LCN {vol_info['mft_start_lcn']:,}")
        print(f"2. MFT byte offset = {vol_info['mft_start_lcn']:,}   {vol_info['bytes_per_cluster']:,} = {mft_start_bytes:,}")
        print(f"3. Record {file_info['mft_record_number']:,} offset = {file_info['mft_record_number']:,}   {vol_info['mft_record_size']:,} = {mft_record_offset:,}")
        print(f"4. Total offset = {mft_start_bytes:,} + {mft_record_offset:,} = {mft_absolute_offset:,}")
        print(f"5. Relative LBA = {mft_absolute_offset:,}   {bytes_per_sector:,} = {mft_lba_rel:,}")
        print(f"6. Absolute LBA = {partition_lba:,} + {mft_lba_rel:,} = {mft_lba_abs:,}")
    
    def analyze_mft_record(self, drive_letter, mft_record_number, show_hex=False):
        """Analyze specific MFT record"""
        vol_info = self.file_analyzer.get_volume_info(drive_letter)
        partition_lba = self.file_analyzer.get_partition_start_lba(drive_letter)
        
        mft_start_bytes = vol_info['mft_start_lcn'] * vol_info['bytes_per_cluster']
        mft_record_offset = mft_record_number * vol_info['mft_record_size']
        mft_absolute_offset = mft_start_bytes + mft_record_offset
        mft_lba_rel = mft_absolute_offset // 512
        mft_lba_abs = partition_lba + mft_lba_rel
        
        print(f"Analyzing MFT record {mft_record_number} from drive {drive_letter}:")
        print("=" * 60)
        print(f"MFT Record LBA (relative): {mft_lba_rel:,}")
        print(f"MFT Record LBA (absolute): {mft_lba_abs:,}")
        print(f"MFT Record Byte Offset: {mft_absolute_offset:,}")
        print()
        
        mft_data = self.mft_parser.read_mft_record(
            drive_letter, vol_info['mft_start_lcn'], vol_info['bytes_per_cluster'],
            vol_info['mft_record_size'], mft_record_number
        )
        
        print(f"Successfully read {len(mft_data)} bytes")
        
        if show_hex:
            print("\n=== Raw MFT Record Data ===")
            print(self.mft_parser.hex_dump(mft_data))
            print()
        
        if mft_data[:4] == b'FILE':
            print("=== MFT Record Analysis ===")
            header = self.mft_parser.parse_mft_header(mft_data)
            print(f"Signature: FILE ( Valid)")
            print(f"Sequence Number: {header['sequence_number']}")
            print(f"Link Count: {header['link_count']}")
            print(f"Flags: 0x{header['flags']:04x} ({header['flags_description']})")
            print(f"Bytes in Use: {header['bytes_in_use']}")
            
            data_attrs = self.mft_parser.parse_mft_attributes(mft_data)
            if data_attrs:
                print(f"\n$DATA Attributes: {len(data_attrs)}")
                for i, attr in enumerate(data_attrs, 1):
                    status = "RESIDENT" if attr['is_resident'] else "NON-RESIDENT"
                    stream = f" ('{attr['stream_name']}')" if attr['stream_name'] else " (unnamed)"
                    print(f"  Attribute {i}: {status}{stream}")
            else:
                print("\nNo $DATA attributes found")
        else:
            print("=== Invalid MFT Record ===")
            print(f"Invalid signature: {mft_data[:4]}")
    
    def test_common_files(self):
        """Test with common system files"""
        print("\n" + "=" * 60)
        print("Testing NTFS Forensics Toolkit:")
        print("=" * 60)
        
        test_files = [
            "C:\\Windows\\win.ini",
            "C:\\Windows\\System32\\drivers\\etc\\hosts"
        ]
        
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"\n{'-' * 50}")
                print(f"Testing: {test_file}")
                print(f"{'-' * 50}")
                try:
                    self.print_file_analysis(test_file)
                except Exception as e:
                    print(f"Error: {e}")

def main():
    if not WindowsAPI.is_admin():
        print("  Run as Administrator")
        return 1
    
    if len(sys.argv) < 2:
        print("Usage: comprehensive_analyzer.py <file_path>")
        return 1
    
    analyzer = ComprehensiveAnalyzer()
    analyzer.print_file_analysis(sys.argv[1])
    return 0

if __name__ == "__main__":
    sys.exit(main())
