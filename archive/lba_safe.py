import os
import sys
import ctypes
from ctypes import wintypes

SECTOR_SIZE = 512
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
FILE_BEGIN = 0
INVALID_HANDLE_VALUE = -1

kernel32 = ctypes.windll.kernel32

def write_without_locking(payload, sector_offset, volume_letter):
    """Write directly without volume locking - works when running from same drive"""
    volume_path = f"\\\\.\\{volume_letter}:"
    
    # Check if we're running from the target drive
    current_drive = os.path.splitdrive(os.getcwd())[0].replace(':', '').upper()
    if current_drive == volume_letter.upper():
        print(f"WARNING: Running from target drive {volume_letter}:, skipping volume lock")
        use_locking = False
    else:
        use_locking = True
    
    # Open volume
    handle = kernel32.CreateFileW(
        volume_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH if use_locking else 0,
        None
    )
    
    if handle == INVALID_HANDLE_VALUE:
        print(f"Error: Cannot open volume {volume_path}")
        return False
    
    try:
        # Skip locking if running from same drive
        if use_locking:
            print("Locking volume...")
            bytes_returned = wintypes.DWORD()
            if not kernel32.DeviceIoControlW(handle, 0x00090018, None, 0, None, 0, ctypes.byref(bytes_returned), None):
                print("Lock failed, continuing without lock...")
        
        # Seek and write
        offset = sector_offset * SECTOR_SIZE
        kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offset), None, FILE_BEGIN)
        
        sector_buffer = ctypes.create_string_buffer(SECTOR_SIZE)
        payload_bytes = payload.encode('utf-8')
        copy_size = min(len(payload_bytes), SECTOR_SIZE)
        ctypes.memmove(sector_buffer, payload_bytes, copy_size)
        
        bytes_written = wintypes.DWORD()
        result = kernel32.WriteFile(handle, sector_buffer, SECTOR_SIZE, ctypes.byref(bytes_written), None)
        
        if result and bytes_written.value == SECTOR_SIZE:
            kernel32.FlushFileBuffers(handle)
            print(f"Successfully wrote {copy_size} bytes to sector {sector_offset}")
            return True
        else:
            print("Write failed")
            return False
            
    finally:
        if use_locking:
            # Unlock
            bytes_returned = wintypes.DWORD()
            kernel32.DeviceIoControlW(handle, 0x0009001C, None, 0, None, 0, ctypes.byref(bytes_returned), None)
        kernel32.CloseHandle(handle)

def main():
    current_drive = os.path.splitdrive(os.getcwd())[0].replace(':', '')
    print(f"Currently running from drive: {current_drive}")
    print(f"Target drive: D")
    
    if current_drive.upper() == 'D':
        print("SOLUTION: Running from target drive - will skip volume locking")
    
    # Test write
    write_without_locking("Test from same drive", 13364696, "D")

if __name__ == "__main__":
    main()