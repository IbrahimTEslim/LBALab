import ctypes
import sys
from ctypes import wintypes

# Windows constants
GENERIC_WRITE = 0x40000000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
INVALID_HANDLE_VALUE = -1
FILE_BEGIN = 0

def get_drive_size(drive_number):
    """Get the total size and sector count of a drive"""
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
    handle = INVALID_HANDLE_VALUE
    
    try:
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        
        if handle == INVALID_HANDLE_VALUE:
            return None, None
        
        file_size = ctypes.c_longlong(0)
        if ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(file_size)):
            total_bytes = file_size.value
            total_sectors = total_bytes // 512
            return total_bytes, total_sectors
        
        return None, None
        
    except:
        return None, None
    finally:
        if handle != INVALID_HANDLE_VALUE:
            ctypes.windll.kernel32.CloseHandle(handle)

def write_to_lba(drive_number, lba, payload, sector_size=512):
    """
    Write data directly to a specific LBA on a drive.
    
    Args:
        drive_number (int): Physical drive number (0, 1, 2, etc.)
        lba (int): Logical Block Address to write to
        payload (bytes): Data to write
        sector_size (int): Sector size (default: 512)
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Validate LBA range first
    total_bytes, total_sectors = get_drive_size(drive_number)
    if total_sectors is None:
        print(f"Cannot determine size of drive {drive_number}")
        return False
    
    if lba >= total_sectors:
        print(f"Error: LBA {lba} exceeds drive capacity of {total_sectors:,} sectors")
        print(f"Maximum valid LBA: {total_sectors - 1:,}")
        return False
    
    print(f"Drive {drive_number}: {total_sectors:,} sectors ({total_bytes / (1024**3):.2f} GB)")
    print(f"Writing to LBA {lba:,} (valid range: 0 to {total_sectors-1:,})")
    
    # Ensure payload is bytes
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    
    # Pad or truncate payload to sector size
    if len(payload) < sector_size:
        payload = payload + b'\x00' * (sector_size - len(payload))
    elif len(payload) > sector_size:
        payload = payload[:sector_size]
        print(f"Warning: Payload truncated to {sector_size} bytes")
    
    drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
    handle = INVALID_HANDLE_VALUE
    
    try:
        print(f"Debug: Attempting to open {drive_path}")
        
        # Try opening with different access levels and flags
        access_modes = [
            (GENERIC_WRITE, 0, "Exclusive write"),
            (GENERIC_WRITE, FILE_SHARE_READ, "Write with read sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, "Write with full sharing"),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, "Read/Write with sharing")
        ]
        
        for access, share, desc in access_modes:
            print(f"Trying: {desc}")
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path,
                access,
                share,
                None,
                OPEN_EXISTING,
                FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH,
                None
            )
            
            if handle != INVALID_HANDLE_VALUE:
                print(f"Success with: {desc}")
                break
            
            error = ctypes.windll.kernel32.GetLastError()
            print(f"Failed: {desc} (Error {error})")
        
        if handle == INVALID_HANDLE_VALUE:
            print("All access methods failed. Trying without buffering flags...")
            
            # Final attempt without special flags
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path,
                GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,  # No special flags
                None
            )
            
            if handle == INVALID_HANDLE_VALUE:
                error = ctypes.windll.kernel32.GetLastError()
                if error == 5:
                    print("Final attempt failed: Access denied")
                    print("Possible causes:")
                    print("- Drive is BitLocker encrypted")
                    print("- Drive has hardware write protection")
                    print("- Antivirus software is blocking access")
                    print("- Drive is mounted as read-only")
                    print("- Another process has exclusive access")
                elif error == 2:
                    print(f"Drive {drive_number} not found")
                elif error == 6:
                    print(f"Invalid handle - drive {drive_number} may not exist")
                else:
                    print(f"Cannot access drive {drive_number}. Error: {error}")
                return False
        
        print(f"Successfully opened {drive_path}")
        
        # Calculate byte offset and validate alignment
        byte_offset = lba * sector_size
        
        # Ensure we're aligned to sector boundaries
        if byte_offset % sector_size != 0:
            print(f"Warning: Byte offset {byte_offset} not aligned to sector size {sector_size}")
        
        print(f"Seeking to byte offset: {byte_offset:,} (LBA {lba:,})")
        
        # Seek to position (handle large offsets)
        low_offset = byte_offset & 0xFFFFFFFF
        high_offset = ctypes.c_long((byte_offset >> 32) & 0xFFFFFFFF)
        
        result = ctypes.windll.kernel32.SetFilePointer(
            handle, 
            low_offset, 
            ctypes.byref(high_offset), 
            FILE_BEGIN
        )
        
        if result == 0xFFFFFFFF:
            error = ctypes.windll.kernel32.GetLastError()
            if error != 0:
                if error == 27:
                    print(f"Sector not found - LBA {lba} may be invalid or beyond drive capacity")
                    print(f"Drive has {total_sectors:,} sectors, you tried LBA {lba:,}")
                else:
                    print(f"Failed to seek to LBA {lba}. Error: {error}")
                return False
        
        print("Seek successful, attempting write...")
        
        # Write the data
        bytes_written = wintypes.DWORD(0)
        success = ctypes.windll.kernel32.WriteFile(
            handle,
            ctypes.c_char_p(payload),
            len(payload),
            ctypes.byref(bytes_written),
            None
        )
        
        if not success:
            error = ctypes.windll.kernel32.GetLastError()
            if error == 5:
                print("Write access denied - drive may be read-only or protected")
            elif error == 27:
                print("Sector not found during write - invalid LBA or drive geometry issue")
            elif error == 33:
                print("Drive is locked by another process")
            elif error == 19:
                print("Drive is write-protected")
            else:
                print(f"Write failed. Error: {error}")
            return False
        
        # Flush buffers
        ctypes.windll.kernel32.FlushFileBuffers(handle)
        
        print(f"Successfully wrote {bytes_written.value} bytes to Drive {drive_number}, LBA {lba}")
        return True
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        if handle != INVALID_HANDLE_VALUE:
            ctypes.windll.kernel32.CloseHandle(handle)

def list_drives():
    """List available physical drives"""
    print("Checking available drives...")
    available_drives = []
    
    for i in range(10):
        drive_path = f"\\\\.\\PhysicalDrive{i}"
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        
        if handle != INVALID_HANDLE_VALUE:
            # Get drive size
            file_size = ctypes.c_longlong(0)
            if ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(file_size)):
                size_gb = file_size.value / (1024**3)
                print(f"Drive {i}: {size_gb:.2f} GB")
                available_drives.append(i)
            else:
                print(f"Drive {i}: Available (size unknown)")
                available_drives.append(i)
            
            ctypes.windll.kernel32.CloseHandle(handle)
    
    if not available_drives:
        print("No drives found. Run as Administrator.")
    
    return available_drives

def is_admin():
    """Check if running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    """Simple interactive interface"""
    print("Simple LBA Writer")
    print("================")
    print("CAUTION: This writes directly to disk sectors!")
    
    # Check admin privileges
    if not is_admin():
        print("\n⚠️  WARNING: Not running as Administrator!")
        print("Physical drive write access requires Administrator privileges.")
        print("Please restart this script as Administrator.")
        print()
        input("Press Enter to continue anyway (will likely fail)...")
    else:
        print("✓ Running with Administrator privileges")
    
    print()
    
    # List available drives
    available_drives = list_drives()
    if not available_drives:
        return
    
    print()
    
    try:
        # Get drive number
        drive_num = int(input("Enter drive number: "))
        if drive_num not in available_drives:
            print(f"Drive {drive_num} not available.")
            return
        
        # Get LBA
        lba = int(input("Enter LBA: "))
        
        # Get payload
        print("\nPayload options:")
        print("1. Text")
        print("2. Hex (e.g., 48656c6c6f)")
        choice = input("Choice (1/2): ").strip()
        
        if choice == "1":
            text = input("Enter text: ")
            payload = text.encode('utf-8')
        elif choice == "2":
            hex_input = input("Enter hex: ")
            try:
                payload = bytes.fromhex(hex_input.replace(" ", ""))
            except ValueError:
                print("Invalid hex format")
                return
        else:
            print("Invalid choice")
            return
        
        # Confirm
        print(f"\nWill write to Drive {drive_num}, LBA {lba}")
        print(f"Payload: {payload[:50]}{'...' if len(payload) > 50 else ''}")
        confirm = input("\nType 'YES' to confirm: ")
        
        if confirm == "YES":
            success = write_to_lba(drive_num, lba, payload)
            if success:
                print("Write completed!")
            else:
                print("Write failed!")
        else:
            print("Cancelled")
    
    except ValueError:
        print("Invalid input")
    except KeyboardInterrupt:
        print("\nCancelled")

# Direct usage example
def simple_write_example():
    """Example of direct function usage"""
    drive_number = 1
    lba = 2048
    payload = b"Hello LBA World!"
    
    print(f"Example: Writing to Drive {drive_number}, LBA {lba}")
    success = write_to_lba(drive_number, lba, payload)
    return success

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        simple_write_example()
    else:
        main()