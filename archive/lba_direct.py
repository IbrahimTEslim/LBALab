import os
import sys
import ctypes
from ctypes import wintypes
import struct

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

# IOCTL codes
FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_UNLOCK_VOLUME = 0x0009001C
FSCTL_DISMOUNT_VOLUME = 0x00090020

# Privilege constants
SE_MANAGE_VOLUME_NAME = "SeManageVolumePrivilege"
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008

# Load Windows API functions
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32

def read_from_volume(sector_offset, volume_letter):
    """Read data from a specific sector on a volume"""
    volume_path = f"\\\\.\\{volume_letter}:"
    
    # Open volume for reading
    handle = kernel32.CreateFileW(
        volume_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING,
        None
    )
    
    if handle == INVALID_HANDLE_VALUE:
        print("Error: Cannot open volume for reading")
        return False
    
    try:
        # Seek to sector
        offset = sector_offset * SECTOR_SIZE
        result = kernel32.SetFilePointerEx(
            handle,
            ctypes.c_longlong(offset),
            None,
            FILE_BEGIN
        )
        
        if not result:
            print(f"Error: Cannot seek to sector {sector_offset}")
            return False
        
        # Read sector
        buffer = ctypes.create_string_buffer(SECTOR_SIZE)
        bytes_read = wintypes.DWORD()
        
        if kernel32.ReadFile(handle, buffer, SECTOR_SIZE, ctypes.byref(bytes_read), None):
            print(f"Read {bytes_read.value} bytes from sector {sector_offset}")
            
            # Display first 64 bytes as hex
            data = buffer.raw[:min(64, bytes_read.value)]
            hex_str = ' '.join(f'{b:02X}' for b in data)
            print(f"First 64 bytes as hex: {hex_str}")
            
            # Display first 64 bytes as text
            text_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
            print(f"First 64 bytes as text: {text_str}")
            
            return True
        else:
            print("Error reading from volume")
            return False
            
    finally:
        kernel32.CloseHandle(handle)

def enable_privilege():
    """Enable SeManageVolumePrivilege"""
    try:
        # Get current process token
        token = wintypes.HANDLE()
        process = kernel32.GetCurrentProcess()
        
        if not advapi32.OpenProcessToken(
            process,
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(token)
        ):
            return False
        
        # Lookup privilege value
        luid = wintypes.LARGE_INTEGER()
        if not advapi32.LookupPrivilegeValueW(
            None,
            SE_MANAGE_VOLUME_NAME,
            ctypes.byref(luid)
        ):
            kernel32.CloseHandle(token)
            return False
        
        # Adjust token privileges
        class TOKEN_PRIVILEGES(ctypes.Structure):
            _fields_ = [
                ("PrivilegeCount", wintypes.DWORD),
                ("Luid", wintypes.LARGE_INTEGER),
                ("Attributes", wintypes.DWORD)
            ]
        
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Luid = luid
        tp.Attributes = SE_PRIVILEGE_ENABLED
        
        result = advapi32.AdjustTokenPrivileges(
            token,
            False,
            ctypes.byref(tp),
            0,
            None,
            None
        )
        
        kernel32.CloseHandle(token)
        return bool(result)
        
    except Exception:
        return False

def write_to_volume(payload, sector_offset, volume_letter):
    """Write data to a specific sector on a volume"""
    # Enable privilege
    if not enable_privilege():
        print("Warning: Could not enable SeManageVolumePrivilege")
    
    volume_path = f"\\\\.\\{volume_letter}:"
    
    print(f"Attempting to open volume: {volume_path}")
    print(f"IMPORTANT: Close any files/folders open on {volume_letter}: drive!")
    input("Press Enter when ready...")
    
    # Open volume
    handle = kernel32.CreateFileW(
        volume_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH,
        None
    )
    
    if handle == INVALID_HANDLE_VALUE:
        error_code = kernel32.GetLastError()
        print(f"Error: Cannot open volume {volume_path}")
        print(f"Error code: {error_code}")
        return False
    
    try:
        # Lock volume
        print("Attempting to lock volume...")
        bytes_returned = wintypes.DWORD()
        if not kernel32.DeviceIoControlW(
            handle,
            FSCTL_LOCK_VOLUME,
            None, 0,
            None, 0,
            ctypes.byref(bytes_returned),
            None
        ):
            error_code = kernel32.GetLastError()
            print(f"Error: Cannot lock volume. Error code: {error_code}")
            print(f"Make sure no programs are using the {volume_letter}: drive")
            return False
        
        print("Volume locked successfully.")
        
        # Dismount volume
        print("Dismounting volume...")
        if not kernel32.DeviceIoControlW(
            handle,
            FSCTL_DISMOUNT_VOLUME,
            None, 0,
            None, 0,
            ctypes.byref(bytes_returned),
            None
        ):
            error_code = kernel32.GetLastError()
            print(f"Warning: Cannot dismount volume. Error code: {error_code}")
        
        # Seek to sector
        offset = sector_offset * SECTOR_SIZE
        if not kernel32.SetFilePointerEx(
            handle,
            ctypes.c_longlong(offset),
            None,
            FILE_BEGIN
        ):
            error_code = kernel32.GetLastError()
            print(f"Error: Cannot seek to sector {sector_offset}")
            print(f"Error code: {error_code}")
            return False
        
        # Prepare sector buffer
        sector_buffer = ctypes.create_string_buffer(SECTOR_SIZE)
        
        # Copy payload to buffer
        payload_bytes = payload.encode('utf-8')
        copy_size = min(len(payload_bytes), SECTOR_SIZE)
        ctypes.memmove(sector_buffer, payload_bytes, copy_size)
        
        # Write sector
        print("Writing sector...")
        bytes_written = wintypes.DWORD()
        result = kernel32.WriteFile(
            handle,
            sector_buffer,
            SECTOR_SIZE,
            ctypes.byref(bytes_written),
            None
        )
        
        if not result or bytes_written.value != SECTOR_SIZE:
            error_code = kernel32.GetLastError()
            print(f"Error: Failed to write complete sector. Written: {bytes_written.value} bytes")
            print(f"Error code: {error_code}")
            return False
        
        # Flush to disk
        if not kernel32.FlushFileBuffers(handle):
            print("Warning: Failed to flush data to disk")
        
        print("Write successful!")
        
        # Unlock volume
        print("Unlocking volume...")
        if not kernel32.DeviceIoControlW(
            handle,
            FSCTL_UNLOCK_VOLUME,
            None, 0,
            None, 0,
            ctypes.byref(bytes_returned),
            None
        ):
            error_code = kernel32.GetLastError()
            print(f"Warning: Cannot unlock volume. Error code: {error_code}")
        
        print(f"Successfully wrote {copy_size} bytes to sector {sector_offset} on volume {volume_letter}:")
        return True
        
    finally:
        kernel32.CloseHandle(handle)

def main():
    # Configuration
    payload = "KilluaKillua"
    sector_offset = 13364696
    volume_letter = "D"
    
    print(f"DEBUG: Writing to sector {sector_offset} on volume {volume_letter}")
    print(f"This corresponds to byte offset: {sector_offset * 512}")
    
    print(f"WARNING: This will directly modify disk sectors on volume {volume_letter}:!")
    print(f'Payload: "{payload}"')
    print(f"Sector: {sector_offset} (relative to volume start)")
    print(f"Volume: {volume_letter}:")
    
    confirm = input("Continue? (y/N): ")
    
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return 0
    
    # Read before writing
    print("\n=== BEFORE WRITE ===")
    read_from_volume(sector_offset, volume_letter)
    
    # Uncomment to enable writing
    if write_to_volume(payload, sector_offset, volume_letter):
        print("Write operation completed successfully.")
        
        # Read after writing to verify
        print("\n=== AFTER WRITE ===")
        read_from_volume(sector_offset, volume_letter)
        
        return 0
    else:
        print("Write operation failed.")
        return 1

if __name__ == "__main__":
    if os.name != 'nt':
        print("This script only works on Windows")
        sys.exit(1)
    
    main()