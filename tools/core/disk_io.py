"""Low-level disk I/O operations"""
import ctypes
from ctypes import wintypes
from .windows_api import *
from .ntfs_structures import *

# Additional constants for writing
FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_UNLOCK_VOLUME = 0x0009001C
FSCTL_DISMOUNT_VOLUME = 0x00090020
FILE_FLAG_WRITE_THROUGH = 0x80000000

class DiskIO:
    """Low-level disk read/write operations"""
    
    def __init__(self):
        self.sector_size = 512
    
    def open_file(self, path):
        """Open file handle"""
        abs_path = path if path.startswith("\\\\?\\") else f"\\\\?\\{path}"
        handle = ctypes.windll.kernel32.CreateFileW(
            abs_path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open file: {path}")
        return handle
    
    def open_volume(self, drive_letter):
        """Open volume handle"""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, 0, None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open volume: {drive_letter}")
        return handle
    
    def open_physical_drive(self, drive_number):
        """Open physical drive handle"""
        drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open PhysicalDrive{drive_number}")
        return handle
    
    def read_lba_physical(self, drive_number, lba, size=None):
        """Read from physical drive at absolute LBA"""
        if size is None:
            size = self.sector_size
        
        handle = self.open_physical_drive(drive_number)
        try:
            byte_offset = lba * self.sector_size
            aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                raise OSError("SetFilePointerEx failed")
            
            buffer = ctypes.create_string_buffer(aligned_size)
            bytes_read = wintypes.DWORD(0)
            
            if not ctypes.windll.kernel32.ReadFile(handle, buffer, aligned_size, ctypes.byref(bytes_read), None):
                raise OSError("ReadFile failed")
            
            return buffer.raw[:size]
        finally:
            WindowsAPI.close_handle(handle)
    
    def read_lba_volume(self, drive_letter, lba_relative, size=None):
        """Read from volume at relative LBA"""
        if size is None:
            size = self.sector_size
        
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open volume {drive_letter}")
        
        try:
            byte_offset = lba_relative * self.sector_size
            aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                raise OSError("SetFilePointerEx failed")
            
            buffer = ctypes.create_string_buffer(aligned_size)
            bytes_read = wintypes.DWORD(0)
            
            if not ctypes.windll.kernel32.ReadFile(handle, buffer, aligned_size, ctypes.byref(bytes_read), None):
                raise OSError("ReadFile failed")
            
            return buffer.raw[:size]
        finally:
            WindowsAPI.close_handle(handle)
    
    def write_lba_physical(self, drive_number, lba, data):
        """Write data to physical drive at specific LBA"""
        if len(data) % self.sector_size != 0:
            # Pad to sector boundary
            data = data + b'\x00' * (self.sector_size - len(data) % self.sector_size)
        
        handle = self.open_physical_drive_write(drive_number)
        try:
            byte_offset = lba * self.sector_size
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                error = ctypes.windll.kernel32.GetLastError()
                raise OSError(f"SetFilePointerEx failed: Error {error} - Cannot seek to LBA {lba}")
            
            bytes_written = wintypes.DWORD(0)
            if not ctypes.windll.kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None):
                error = ctypes.windll.kernel32.GetLastError()
                if error == 5:
                    raise OSError(f"WriteFile failed: Access denied - drive may be write-protected")
                elif error == 27:
                    raise OSError(f"WriteFile failed: Sector not found - LBA {lba} may be invalid")
                elif error == 33:
                    raise OSError(f"WriteFile failed: Drive locked by another process")
                else:
                    raise OSError(f"WriteFile failed: Error {error}")
            
            if not ctypes.windll.kernel32.FlushFileBuffers(handle):
                error = ctypes.windll.kernel32.GetLastError()
                raise OSError(f"FlushFileBuffers failed: Error {error} - Data may not be written to disk")
            
            return bytes_written.value
        finally:
            WindowsAPI.close_handle(handle)
    
    def write_lba_volume(self, drive_letter, lba_relative, data):
        """Write data to volume at relative LBA - NO LOCKING (like working archive)"""
        if len(data) % self.sector_size != 0:
            data = data + b'\x00' * (self.sector_size - len(data) % self.sector_size)
        
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        
        # Try multiple access modes (like working archive version)
        access_modes = [
            (GENERIC_WRITE, 0, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Exclusive write"),
            (GENERIC_WRITE, FILE_SHARE_READ, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with read sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with full sharing"),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Read/Write with sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, "Write without buffering flags"),
        ]
        
        print(f"Attempting to open volume {volume_path} for writing...")
        
        handle = -1
        for access, share, flags, desc in access_modes:
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, access, share, None, OPEN_EXISTING, flags, None
            )
            
            if handle != -1:
                print(f"✓ Successfully opened with: {desc}")
                break
            
            error = ctypes.windll.kernel32.GetLastError()
            print(f"✗ Failed ({desc}): Error {error}")
            
            if error == 5:
                print(f"   → Access denied - volume may be locked or in use")
            elif error == 32:
                print(f"   → Volume is in use by another process")
            elif error == 19:
                print(f"   → Volume is write-protected")
        
        if handle == -1:
            raise OSError(f"Cannot open volume {drive_letter} for writing (all {len(access_modes)} methods failed)")
        
        try:
            # Write directly without locking (like working archive)
            byte_offset = lba_relative * self.sector_size
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                error = ctypes.windll.kernel32.GetLastError()
                raise OSError(f"SetFilePointerEx failed: Error {error} - Cannot seek to LBA {lba_relative}")
            
            bytes_written = wintypes.DWORD(0)
            if not ctypes.windll.kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None):
                error = ctypes.windll.kernel32.GetLastError()
                if error == 5:
                    raise OSError(f"WriteFile failed: Access denied - volume may be write-protected")
                elif error == 27:
                    raise OSError(f"WriteFile failed: Sector not found - LBA {lba_relative} may be invalid")
                elif error == 33:
                    raise OSError(f"WriteFile failed: Volume locked by another process")
                else:
                    raise OSError(f"WriteFile failed: Error {error}")
            
            ctypes.windll.kernel32.FlushFileBuffers(handle)
            
            return bytes_written.value
        finally:
            WindowsAPI.close_handle(handle)
    
    def open_physical_drive_write(self, drive_number):
        """Open physical drive with write access - tries multiple modes"""
        drive_path = f"\\\\.\\{drive_number}:"
        
        # Try multiple access modes (like working archive version)
        access_modes = [
            (GENERIC_WRITE, 0, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Exclusive write"),
            (GENERIC_WRITE, FILE_SHARE_READ, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with read sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with full sharing"),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Read/Write with sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, "Write without buffering flags"),
        ]
        
        print(f"Attempting to open {drive_path} for writing...")
        
        for access, share, flags, desc in access_modes:
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path, access, share, None, OPEN_EXISTING, flags, None
            )
            
            if handle != -1:
                print(f"✓ Successfully opened with: {desc}")
                return handle
            
            error = ctypes.windll.kernel32.GetLastError()
            print(f"✗ Failed ({desc}): Error {error}")
            
            # Add specific error explanations
            if error == 5:
                print(f"   → Access denied - possible causes:")
                print(f"     - Not running as Administrator")
                print(f"     - Drive is BitLocker encrypted")
                print(f"     - Antivirus blocking access")
            elif error == 2:
                print(f"   → Drive {drive_number} not found")
            elif error == 32:
                print(f"   → Drive is in use by another process")
        
        raise OSError(f"Cannot open PhysicalDrive{drive_number} for writing (all {len(access_modes)} methods failed)")

    def get_physical_drive_number(self, drive_letter):
        handle = self.open_volume(drive_letter)
        try:
            buffer = ctypes.create_string_buffer(64)
            returned = wintypes.DWORD()
            
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                None, 0, buffer, 64, ctypes.byref(returned), None
            ):
                raise OSError("DeviceIoControl failed")
            
            return int.from_bytes(buffer[8:12], 'little')
        finally:
            WindowsAPI.close_handle(handle)
