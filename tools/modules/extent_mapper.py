#!/usr/bin/env python3
"""
Extent Mapper - Map file VCN   LCN   LBA
Can be run standalone or imported
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import DiskIO, WindowsAPI
from core.ntfs_structures import *
from modules.file_analyzer import FileAnalyzer
import ctypes
from ctypes import wintypes

class ExtentMapper:
    """Map file extents to physical disk locations"""
    
    def __init__(self):
        self.disk_io = DiskIO()
        self.analyzer = FileAnalyzer()
    
    def get_file_extents(self, file_path):
        """Get file extents (VCN   LCN mapping)"""
        handle = self.disk_io.open_file(file_path)
        try:
            input_buffer = STARTING_VCN_INPUT_BUFFER(0)
            out_size = 8192
            output_buffer = ctypes.create_string_buffer(out_size)
            returned = wintypes.DWORD()
            
            res = ctypes.windll.kernel32.DeviceIoControl(
                handle, 0x90073,  # FSCTL_GET_RETRIEVAL_POINTERS
                ctypes.byref(input_buffer), ctypes.sizeof(input_buffer),
                output_buffer, out_size, ctypes.byref(returned), None
            )
            
            if not res:
                err = ctypes.GetLastError()
                # Error 1 = ERROR_INVALID_FUNCTION (resident file)
                # Error 38 = ERROR_HANDLE_EOF (resident file, no extents)
                if err in (1, 38):
                    return None
                raise OSError(f"DeviceIoControl failed: {err}")
            
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
                    lcn = int.from_bytes(lcn_raw, 'little', signed=True)
                    if lcn < 0:
                        lcn = -1
                
                extents.append((current_vcn, next_vcn, lcn))
                current_vcn = next_vcn
            
            return extents
        finally:
            WindowsAPI.close_handle(handle)
    
    def map_extents_to_lba(self, file_path):
        """Map file extents to LBA addresses"""
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        
        # Get volume info
        vol_info = self.analyzer.get_volume_info(drive_letter)
        partition_lba = self.analyzer.get_partition_start_lba(drive_letter)
        sectors_per_cluster, bytes_per_sector = self.analyzer.get_sectors_per_cluster(drive_letter)
        
        # Get extents
        extents = self.get_file_extents(file_path)
        
        if extents is None:
            return {"is_resident": True, "extents": []}
        
        # Map to LBA
        lba_mappings = []
        for start_vcn, next_vcn, lcn in extents:
            cluster_count = next_vcn - start_vcn
            
            if lcn == -1:
                lba_mappings.append({
                    "start_vcn": start_vcn,
                    "next_vcn": next_vcn,
                    "cluster_count": cluster_count,
                    "type": "sparse"
                })
            else:
                lcn_relative_lba = lcn * sectors_per_cluster
                absolute_lba = partition_lba + lcn_relative_lba
                byte_offset = absolute_lba * bytes_per_sector
                size_bytes = cluster_count * vol_info['bytes_per_cluster']
                
                lba_mappings.append({
                    "start_vcn": start_vcn,
                    "next_vcn": next_vcn,
                    "cluster_count": cluster_count,
                    "lcn": lcn,
                    "lba_relative": lcn_relative_lba,
                    "lba_absolute": absolute_lba,
                    "byte_offset": byte_offset,
                    "size_bytes": size_bytes,
                    "type": "allocated"
                })
        
        return {
            "is_resident": False,
            "extents": lba_mappings,
            "partition_lba": partition_lba,
            "sectors_per_cluster": sectors_per_cluster
        }

def main():
    """Standalone CLI"""
    if not WindowsAPI.is_admin():
        print("  Run as Administrator")
        return 1
    
    if len(sys.argv) < 2:
        print("Usage: extent_mapper.py <file_path>")
        return 1
    
    mapper = ExtentMapper()
    file_path = sys.argv[1]
    
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return 1
        
        print(f"Mapping extents for: {file_path}")
        print("=" * 60)
        
        result = mapper.map_extents_to_lba(file_path)
        
        if result['is_resident']:
            print("\nFile is RESIDENT (data stored in MFT record)")
            return 0
        
        print(f"\nFile is NON-RESIDENT")
        print(f"Partition Start LBA: {result['partition_lba']:,}")
        print(f"Sectors per Cluster: {result['sectors_per_cluster']}")
        print(f"\n=== Extents (VCN   LCN   LBA) ===")
        
        for i, extent in enumerate(result['extents'], 1):
            if extent['type'] == 'sparse':
                print(f"\nExtent {i}: VCN {extent['start_vcn']}-{extent['next_vcn']-1} ({extent['cluster_count']} clusters)")
                print(f"  Type: SPARSE (not allocated)")
            else:
                print(f"\nExtent {i}: VCN {extent['start_vcn']}-{extent['next_vcn']-1} ({extent['cluster_count']} clusters, {extent['size_bytes']:,} bytes)")
                print(f"  LCN: {extent['lcn']:,}")
                print(f"  LBA (relative): {extent['lba_relative']:,}")
                print(f"  LBA (absolute): {extent['lba_absolute']:,}")
                print(f"  Byte offset: {extent['byte_offset']:,}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
