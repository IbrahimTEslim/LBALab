#!/usr/bin/env python3
"""Verify all functions from original are in modules"""
import os

# All functions from original file
ORIGINAL_FUNCTIONS = [
    'print_file_analysis', 'main', 'read_lba', 'get_ntfs_volume_data',
    'read_mft_record', 'analyze_mft_record_header', 'get_physical_drive_number',
    'get_file_extents', 'open_file', 'open_volume', 'read_lba_from_volume',
    'safe_handle_close', 'get_file_info', 'hex_dump', 'analyze_mft_record',
    'open_physical_drive', 'analyze_file_complete', 'get_sectors_per_cluster',
    'is_admin', 'is_file_resident', 'parse_mft_attributes',
    'get_partition_start_lba', 'test_common_files', 'map_extents_to_lba',
    'parse_mft_header', 'get_volume_info', 'read_physical', 'read_volume'
]

# Module files to check
MODULE_FILES = [
    'core/windows_api.py',
    'core/disk_io.py', 
    'core/ntfs_structures.py',
    'modules/lba_reader.py',
    'modules/file_analyzer.py',
    'modules/extent_mapper.py',
    'modules/mft_parser.py',
    'modules/residency_checker.py',
    'modules/comprehensive_analyzer.py',
    'cli.py'
]

def check_function(func_name):
    """Check if function exists in any module"""
    for module_file in MODULE_FILES:
        if not os.path.exists(module_file):
            continue
        try:
            with open(module_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if f'def {func_name}(' in content:
                    return True, module_file
        except Exception as e:
            print(f"Error reading {module_file}: {e}")
    return False, None

def main():
    print("=" * 80)
    print("VERIFICATION: All Functions from Original to Modules")
    print("=" * 80)
    print()
    
    found_count = 0
    missing = []
    
    for func in sorted(ORIGINAL_FUNCTIONS):
        exists, location = check_function(func)
        if exists:
            found_count += 1
            print(f"OK {func:35s} -> {location}")
        else:
            missing.append(func)
            print(f"MISSING {func:35s} -> NOT FOUND")
    
    print()
    print("=" * 80)
    print(f"RESULT: {found_count}/{len(ORIGINAL_FUNCTIONS)} functions found")
    
    if missing:
        print(f"\nMISSING {len(missing)} FUNCTIONS:")
        for m in missing:
            print(f"   - {m}")
        return 1
    else:
        print("\nALL FUNCTIONS PRESENT - 100% COMPLETE!")
        return 0

if __name__ == "__main__":
    exit(main())
