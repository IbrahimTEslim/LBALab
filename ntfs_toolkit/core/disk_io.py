"""Low-level disk I/O — read operations and handle management."""
import os
import ctypes
from ctypes import wintypes

from .windows_api import (
    GENERIC_READ, FILE_SHARE_READ, FILE_SHARE_WRITE, FILE_SHARE_DELETE,
    OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_NO_BUFFERING,
    INVALID_HANDLE_VALUE, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
    IOCTL_DISK_GET_DRIVE_GEOMETRY, WindowsAPI,
)
from .ntfs_structures import SECTOR_SIZE
from .privileges import enable_manage_volume_privilege


class DiskIO:
    """Low-level disk read operations and handle management.

    For write operations, use :class:`DiskWriter` from ``ntfs_toolkit.core.disk_writer``.
    """

    def __init__(self, verbose=False):
        self.sector_size = SECTOR_SIZE
        self.verbose = verbose
        enable_manage_volume_privilege(verbose=verbose)

    def _log(self, msg):
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    # Handle helpers
    # ------------------------------------------------------------------

    def open_file(self, path):
        """Open file handle for reading."""
        abs_path = os.path.abspath(path)
        if not abs_path.startswith("\\\\?\\"):
            abs_path = f"\\\\?\\{abs_path}"
        handle = ctypes.windll.kernel32.CreateFileW(
            abs_path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open file: {path}")
        return handle

    def open_volume(self, drive_letter):
        """Open volume handle for reading."""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, 0, None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open volume: {drive_letter}")
        return handle

    def open_physical_drive(self, drive_number):
        """Open physical drive handle for reading."""
        drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open PhysicalDrive{drive_number}")
        return handle

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def read_lba_physical(self, drive_number, lba, size=None):
        """Read from physical drive at absolute LBA."""
        if size is None:
            size = self.sector_size
        handle = self.open_physical_drive(drive_number)
        try:
            return self._read_at_offset(handle, lba * self.sector_size, size)
        finally:
            WindowsAPI.close_handle(handle)

    def read_lba_volume(self, drive_letter, lba_relative, size=None):
        """Read from volume at relative LBA."""
        if size is None:
            size = self.sector_size
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(f"Cannot open volume {drive_letter}")
        try:
            return self._read_at_offset(handle, lba_relative * self.sector_size, size)
        finally:
            WindowsAPI.close_handle(handle)

    def _read_at_offset(self, handle, byte_offset, size):
        """Seek + read with sector alignment."""
        aligned_size = ((size + self.sector_size - 1) // self.sector_size) * self.sector_size
        if not ctypes.windll.kernel32.SetFilePointerEx(
            handle, ctypes.c_longlong(byte_offset), None, 0
        ):
            raise OSError("SetFilePointerEx failed")
        buffer = ctypes.create_string_buffer(aligned_size)
        bytes_read = wintypes.DWORD(0)
        if not ctypes.windll.kernel32.ReadFile(
            handle, buffer, aligned_size, ctypes.byref(bytes_read), None
        ):
            raise OSError("ReadFile failed")
        return buffer.raw[:size]

    # ------------------------------------------------------------------
    # Drive info helpers
    # ------------------------------------------------------------------

    def detect_sector_size(self, drive_number):
        """Detect actual sector size of physical drive."""
        try:
            handle = self.open_physical_drive(drive_number)
            try:
                buffer = ctypes.create_string_buffer(512)
                returned = wintypes.DWORD()
                if ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_DISK_GET_DRIVE_GEOMETRY,
                    None, 0, buffer, 512, ctypes.byref(returned), None,
                ):
                    # DISK_GEOMETRY: BytesPerSector at offset 24 (4 bytes)
                    if returned.value >= 28:
                        bps = int.from_bytes(buffer[24:28], "little")
                        if bps > 0:
                            return bps
                return 512
            finally:
                WindowsAPI.close_handle(handle)
        except Exception:
            return 512

    def get_physical_drive_number(self, drive_letter):
        """Get physical drive number for a volume letter."""
        handle = self.open_volume(drive_letter)
        try:
            buffer = ctypes.create_string_buffer(64)
            returned = wintypes.DWORD()
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                None, 0, buffer, 64, ctypes.byref(returned), None,
            ):
                raise OSError("DeviceIoControl failed")
            return int.from_bytes(buffer[8:12], "little")
        finally:
            WindowsAPI.close_handle(handle)
