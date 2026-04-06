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

# Privilege constants
SE_MANAGE_VOLUME_PRIVILEGE = "SeManageVolumePrivilege"
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", wintypes.LARGE_INTEGER),
        ("Attributes", wintypes.DWORD)
    ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1)
    ]

class DiskIO:
    """Low-level disk read/write operations"""
    
    def __init__(self, enable_aggressive_write=False):
        self.sector_size = 512  # Default, will be detected dynamically
        self.enable_aggressive_write = enable_aggressive_write
        self.enable_manage_volume_privilege()
        
        if self.enable_aggressive_write:
            print(f"   AGGRESSIVE WRITE MODE ENABLED")
            print(f"     Will attempt disk offline/dismount operations")
            print(f"     Use with caution - may affect system stability")
        else:
            print(f"  Safe write mode - disk offline/dismount disabled")
    
    def enable_manage_volume_privilege(self):
        """Enable SeManageVolumePrivilege for advanced disk operations"""
        try:
            print(f"  Enabling SeManageVolumePrivilege...")
            
            # Get current process token
            h_token = wintypes.HANDLE()
            if not ctypes.windll.advapi32.OpenProcessToken(
                ctypes.windll.kernel32.GetCurrentProcess(),
                TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES,
                ctypes.byref(h_token)
            ):
                print(f"   Could not open process token for privilege adjustment")
                return False
            
            try:
                # Get LUID for the privilege
                luid = wintypes.LARGE_INTEGER()
                if not ctypes.windll.advapi32.LookupPrivilegeValueW(
                    None, SE_MANAGE_VOLUME_PRIVILEGE, ctypes.byref(luid)
                ):
                    print(f"   SeManageVolumePrivilege not available on this system")
                    return False
                
                # Prepare token privileges structure
                token_privs = TOKEN_PRIVILEGES()
                token_privs.PrivilegeCount = 1
                token_privs.Privileges[0].Luid = luid
                token_privs.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
                
                # Adjust token privileges
                if ctypes.windll.advapi32.AdjustTokenPrivileges(
                    h_token, False, ctypes.byref(token_privs),
                    ctypes.sizeof(TOKEN_PRIVILEGES), None, None
                ):
                    error = ctypes.windll.kernel32.GetLastError()
                    if error == 0:
                        print(f"  SeManageVolumePrivilege enabled successfully")
                        return True
                    else:
                        print(f"   Failed to enable SeManageVolumePrivilege: Error {error}")
                        return False
                else:
                    error = ctypes.windll.kernel32.GetLastError()
                    print(f"   AdjustTokenPrivileges failed: Error {error}")
                    return False
            
            finally:
                ctypes.windll.kernel32.CloseHandle(h_token)
                
        except Exception as e:
            print(f"   Privilege adjustment failed: {e}")
            return False
    
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
    
    def detect_sector_size(self, drive_number):
        """Detect actual sector size of physical drive"""
        try:
            print(f"  Detecting sector size for PhysicalDrive{drive_number}...")
            handle = self.open_physical_drive(drive_number)
            try:
                # Try to get geometry
                buffer = ctypes.create_string_buffer(512)
                returned = wintypes.DWORD()
                
                # IOCTL_DISK_GET_DRIVE_GEOMETRY
                IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
                
                if ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_DISK_GET_DRIVE_GEOMETRY,
                    None, 0, buffer, 512, ctypes.byref(returned), None
                ):
                    # Parse geometry (simplified)
                    bytes_per_sector = int.from_bytes(buffer(0, 4), 'little')
                    if bytes_per_sector > 0:
                        print(f"  Detected sector size: {bytes_per_sector} bytes")
                        return bytes_per_sector
                
                print(f"   Could not detect sector size, using default 512")
                return 512
            finally:
                WindowsAPI.close_handle(handle)
        except Exception as e:
            print(f"   Sector size detection failed: {e}")
            return 512

    def dismount_volume(self, drive_letter):
        """Dismount volume to enable raw write access"""
        try:
            print(f"  Dismounting volume {drive_letter.upper()}:...")
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            
            # Open volume with dismount privileges
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            
            if handle == INVALID_HANDLE_VALUE:
                error = ctypes.windll.kernel32.GetLastError()
                print(f"   Could not open volume for dismount: Error {error}")
                return False
            
            try:
                # Dismount the volume
                bytes_returned = wintypes.DWORD()
                if ctypes.windll.kernel32.DeviceIoControl(
                    handle, FSCTL_DISMOUNT_VOLUME,
                    None, 0, None, 0, ctypes.byref(bytes_returned), None
                ):
                    print(f"  Volume {drive_letter.upper()}: dismounted successfully")
                    return True
                else:
                    error = ctypes.windll.kernel32.GetLastError()
                    print(f"   Dismount failed: Error {error}")
                    return False
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"   Dismount operation failed: {e}")
            return False
    
    def take_disk_offline(self, drive_number):
        """Take physical disk offline to enable raw write access"""
        try:
            print(f"  Taking PhysicalDrive{drive_number} offline...")
            drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
            
            # Open physical drive
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            
            if handle == INVALID_HANDLE_VALUE:
                error = ctypes.windll.kernel32.GetLastError()
                print(f"   Could not open disk for offline operation: Error {error}")
                return False
            
            try:
                # Take disk offline (IOCTL_DISK_OFFLINE)
                IOCTL_DISK_OFFLINE = 0x00070020
                bytes_returned = wintypes.DWORD()
                
                if ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_DISK_OFFLINE,
                    None, 0, None, 0, ctypes.byref(bytes_returned), None
                ):
                    print(f"  PhysicalDrive{drive_number} taken offline successfully")
                    return True
                else:
                    error = ctypes.windll.kernel32.GetLastError()
                    print(f"   Offline operation failed: Error {error}")
                    return False
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                
        except Exception as e:
            print(f"   Disk offline operation failed: {e}")
            return False

    def write_lba_physical(self, drive_number, lba, data):
        """Write data to physical drive at specific LBA"""
        print(f"=== PHYSICAL DRIVE WRITE DIAGNOSTICS ===")
        print(f"Drive: {drive_number}, LBA: {lba}, Data size: {len(data)} bytes")
        
        # Detect sector size
        detected_sector_size = self.detect_sector_size(drive_number)
        if detected_sector_size != self.sector_size:
            print(f"  Using detected sector size: {detected_sector_size}")
            self.sector_size = detected_sector_size
        
        print(f"Using sector size: {self.sector_size}")
        
        # Try to take disk offline first (only if aggressive mode enabled)
        if self.enable_aggressive_write:
            print(f"  Attempting to bypass Error 5 with disk operations...")
            print(f"   WARNING: This will affect system drive access!")
            self.take_disk_offline(drive_number)
        else:
            print(f"   Safe mode - skipping disk offline operations")
        
        # Validate data alignment
        if len(data) % self.sector_size != 0:
            print(f"   Data size {len(data)} not aligned to sector size {self.sector_size}")
            original_size = len(data)
            data = data + b'\x00' * (self.sector_size - len(data) % self.sector_size)
            print(f"  Padded from {original_size} to {len(data)} bytes")
        else:
            print(f"  Data already aligned to sector boundaries")
        
        # Get drive geometry for validation
        try:
            print(f"  Checking drive geometry...")
            handle_test = self.open_physical_drive(drive_number)
            try:
                # Try to get drive size
                file_size = ctypes.c_longlong(0)
                if ctypes.windll.kernel32.GetFileSizeEx(handle_test, ctypes.byref(file_size)):
                    total_bytes = file_size.value
                    total_sectors = total_bytes // self.sector_size
                    print(f"  Drive size: {total_bytes:,} bytes ({total_sectors:,} sectors)")
                    
                    if lba >= total_sectors:
                        print(f"  ERROR: LBA {lba} exceeds drive capacity!")
                        print(f"   Maximum valid LBA: {total_sectors - 1:,}")
                        raise OSError(f"LBA {lba} out of range (max: {total_sectors - 1})")
                    else:
                        print(f"  LBA {lba} is within valid range")
                else:
                    print(f"   Could not determine drive size")
            finally:
                WindowsAPI.close_handle(handle_test)
        except Exception as e:
            print(f"   Drive geometry check failed: {e}")
        
        print(f"  Attempting to open drive for writing...")
        handle = self.open_physical_drive_write(drive_number)
        
        try:
            byte_offset = lba * self.sector_size
            print(f"  Seeking to byte offset: {byte_offset:,} (LBA {lba}   {self.sector_size})")
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                error = ctypes.windll.kernel32.GetLastError()
                print(f"  SetFilePointerEx failed: Error {error}")
                if error == 31:
                    print(f"     ERROR 31: A device attached to the system is not functioning")
                    print(f"     Possible causes: Drive disconnected, hardware issue, or USB problem")
                elif error == 27:
                    print(f"     ERROR 27: The drive cannot find the sector requested")
                    print(f"     LBA {lba} may be invalid or beyond drive capacity")
                else:
                    print(f"     Unknown seek error")
                raise OSError(f"SetFilePointerEx failed: Error {error} - Cannot seek to LBA {lba}")
            
            print(f"  Successfully positioned to LBA {lba}")
            
            print(f"  Attempting to write {len(data)} bytes...")
            bytes_written = wintypes.DWORD(0)
            if not ctypes.windll.kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None):
                error = ctypes.windll.kernel32.GetLastError()
                print(f"  WriteFile failed: Error {error}")
                
                if error == 5:
                    print(f"     ERROR 5: Access denied (disk offline didn't help)")
                    print(f"     Remaining causes:")
                    print(f"     - Hardware write protection (USB controller)")
                    print(f"     - Firmware-level blocking")
                    print(f"     - Physical write-protect switch")
                    print(f"     - USB drive in read-only mode")
                    print(f"     Try: Different USB drive or volume-level write")
                elif error == 27:
                    print(f"     ERROR 27: Sector not found")
                    print(f"     LBA {lba} may be invalid or drive geometry issue")
                elif error == 33:
                    print(f"     ERROR 33: Drive locked by another process")
                    print(f"     Another application has exclusive access")
                elif error == 19:
                    print(f"     ERROR 19: Media is write-protected")
                    print(f"     Hardware write protection or read-only media")
                elif error == 87:
                    print(f"     ERROR 87: Invalid parameter")
                    print(f"     Possible sector size mismatch or alignment issue")
                elif error == 111:
                    print(f"     ERROR 111: Buffer too small")
                    print(f"     Data size issue or alignment problem")
                else:
                    print(f"     Unknown write error")
                
                raise OSError(f"WriteFile failed: Error {error}")
            
            print(f"  WriteFile succeeded: {bytes_written.value} bytes written")
            
            print(f"  Flushing buffers to ensure data is written to disk...")
            if not ctypes.windll.kernel32.FlushFileBuffers(handle):
                error = ctypes.windll.kernel32.GetLastError()
                print(f"   FlushFileBuffers failed: Error {error}")
                print(f"     Data may not be physically written to disk")
                raise OSError(f"FlushFileBuffers failed: Error {error} - Data may not be written to disk")
            
            print(f"  FlushFileBuffers succeeded")
            print(f"  SUCCESS: Wrote {bytes_written.value} bytes to PhysicalDrive{drive_number} LBA {lba}")
            return bytes_written.value
        finally:
            WindowsAPI.close_handle(handle)
    
    def write_lba_volume(self, drive_letter, lba_relative, data):
        """Write data to volume at relative LBA - NO LOCKING (like working archive)"""
        print(f"=== VOLUME WRITE DIAGNOSTICS ===")
        print(f"Volume: {drive_letter.upper()}, LBA: {lba_relative}, Data size: {len(data)} bytes")
        print(f"Sector size: {self.sector_size}")
        
        # Check if volume is BitLocker encrypted
        try:
            print(f"  Checking BitLocker status...")
            import subprocess
            try:
                result = subprocess.run(['manage-bde', '-status', f'{drive_letter}:'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    if 'BitLocker on' in result.stdout or 'Encryption Percentage' in result.stdout:
                        print(f"   BitLocker is ACTIVE on volume {drive_letter.upper()}")
                        print(f"     This likely blocks raw disk writes for security")
                        print(f"     Try physical drive write instead")
                    else:
                        print(f"  BitLocker is not active on volume {drive_letter.upper()}")
                else:
                    print(f"   Could not determine BitLocker status")
            except:
                print(f"   BitLocker check failed (manage-bde not available)")
        except Exception as e:
            print(f"   BitLocker status check failed: {e}")
        
        # Validate data alignment
        if len(data) % self.sector_size != 0:
            print(f"   Data size {len(data)} not aligned to sector size {self.sector_size}")
            original_size = len(data)
            data = data + b'\x00' * (self.sector_size - len(data) % self.sector_size)
            print(f"  Padded from {original_size} to {len(data)} bytes")
        else:
            print(f"  Data already aligned to sector boundaries")
        
        # Get volume geometry
        try:
            print(f"  Checking volume geometry...")
            handle_test = self.open_volume(drive_letter)
            try:
                file_size = ctypes.c_longlong(0)
                if ctypes.windll.kernel32.GetFileSizeEx(handle_test, ctypes.byref(file_size)):
                    total_bytes = file_size.value
                    total_sectors = total_bytes // self.sector_size
                    print(f"  Volume size: {total_bytes:,} bytes ({total_sectors:,} sectors)")
                    
                    if lba_relative >= total_sectors:
                        print(f"  ERROR: LBA {lba_relative} exceeds volume capacity!")
                        print(f"   Maximum valid LBA: {total_sectors - 1:,}")
                        raise OSError(f"LBA {lba_relative} out of range (max: {total_sectors - 1})")
                    else:
                        print(f"  LBA {lba_relative} is within valid range")
                else:
                    print(f"   Could not determine volume size")
            finally:
                WindowsAPI.close_handle(handle_test)
        except Exception as e:
            print(f"   Volume geometry check failed: {e}")
        
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        
        # Try multiple access modes (like working archive version)
        access_modes = [
            (GENERIC_WRITE, 0, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Exclusive write"),
            (GENERIC_WRITE, FILE_SHARE_READ, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with read sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Write with full sharing"),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH, "Read/Write with sharing"),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, "Write without buffering flags"),
        ]
        
        print(f"  Attempting to open volume {volume_path} for writing...")
        
        handle = -1
        for access, share, flags, desc in access_modes:
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, access, share, None, OPEN_EXISTING, flags, None
            )
            
            if handle != -1:
                print(f"  Successfully opened with: {desc}")
                break
            
            error = ctypes.windll.kernel32.GetLastError()
            print(f"  Failed ({desc}): Error {error}")
            
            if error == 5:
                print(f"     Access denied - volume may be locked or in use")
                print(f"     Possible causes:")
                print(f"     - Volume is BitLocker encrypted")
                print(f"     - Volume is mounted as read-only")
                print(f"     - Another process has exclusive access")
                print(f"     - Not running as Administrator")
            elif error == 32:
                print(f"     Volume is in use by another process")
            elif error == 19:
                print(f"     Volume is write-protected")
            elif error == 1:
                print(f"     Incorrect function - volume may not support raw writes")
        
        if handle == -1:
            raise OSError(f"Cannot open volume {drive_letter} for writing (all {len(access_modes)} methods failed)")
        
        try:
            # Write directly without locking (like working archive)
            byte_offset = lba_relative * self.sector_size
            print(f"  Seeking to byte offset: {byte_offset:,} (LBA {lba_relative}   {self.sector_size})")
            
            if not ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(byte_offset), None, 0):
                error = ctypes.windll.kernel32.GetLastError()
                print(f"  SetFilePointerEx failed: Error {error}")
                if error == 31:
                    print(f"     ERROR 31: Device not functioning")
                elif error == 27:
                    print(f"     ERROR 27: Sector not found")
                else:
                    print(f"     Unknown seek error")
                raise OSError(f"SetFilePointerEx failed: Error {error} - Cannot seek to LBA {lba_relative}")
            
            print(f"  Successfully positioned to LBA {lba_relative}")
            
            print(f"  Attempting to write {len(data)} bytes...")
            bytes_written = wintypes.DWORD(0)
            if not ctypes.windll.kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None):
                error = ctypes.windll.kernel32.GetLastError()
                print(f"  WriteFile failed: Error {error}")
                
                if error == 5:
                    print(f"     ERROR 5: Access denied")
                    print(f"     Possible causes:")
                    print(f"     - Volume is BitLocker encrypted (blocks raw writes)")
                    print(f"     - Volume is write-protected by Windows")
                    print(f"     - Antivirus/EDR blocking raw writes")
                    print(f"     - Windows Defender ransomware protection")
                    print(f"     - Not running as Administrator")
                elif error == 27:
                    print(f"     ERROR 27: Sector not found")
                    print(f"     LBA {lba_relative} may be invalid")
                elif error == 33:
                    print(f"     ERROR 33: Volume locked by another process")
                elif error == 19:
                    print(f"     ERROR 19: Media is write-protected")
                elif error == 87:
                    print(f"     ERROR 87: Invalid parameter")
                    print(f"     Possible sector size or alignment issue")
                elif error == 111:
                    print(f"     ERROR 111: Buffer too small")
                else:
                    print(f"     Unknown write error")
                
                raise OSError(f"WriteFile failed: Error {error}")
            
            print(f"  WriteFile succeeded: {bytes_written.value} bytes written")
            
            print(f"  Flushing buffers...")
            ctypes.windll.kernel32.FlushFileBuffers(handle)
            print(f"  FlushFileBuffers succeeded")
            
            print(f"  SUCCESS: Wrote {bytes_written.value} bytes to Volume {drive_letter.upper()} LBA {lba_relative}")
            return bytes_written.value
        finally:
            WindowsAPI.close_handle(handle)
    
    def open_physical_drive_write(self, drive_number):
        """Open physical drive with write access - tries multiple modes"""
        drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
        
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
                print(f"  Successfully opened with: {desc}")
                return handle
            
            error = ctypes.windll.kernel32.GetLastError()
            print(f"  Failed ({desc}): Error {error}")
            
            # Add specific error explanations
            if error == 5:
                print(f"     Access denied - possible causes:")
                print(f"     - Not running as Administrator")
                print(f"     - Drive is BitLocker encrypted")
                print(f"     - Antivirus blocking access")
            elif error == 2:
                print(f"     Drive {drive_number} not found")
            elif error == 32:
                print(f"     Drive is in use by another process")
        
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
