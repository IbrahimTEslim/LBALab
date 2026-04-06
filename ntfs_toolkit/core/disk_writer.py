"""Low-level disk write operations — DANGEROUS, opt-in only."""
import ctypes
from ctypes import wintypes

from .windows_api import (
    GENERIC_READ, GENERIC_WRITE, FILE_SHARE_READ, FILE_SHARE_WRITE,
    OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, FILE_FLAG_WRITE_THROUGH,
    INVALID_HANDLE_VALUE, FSCTL_DISMOUNT_VOLUME, WindowsAPI,
)
from .disk_io import DiskIO


class DiskWriter(DiskIO):
    """Extends DiskIO with write capabilities.

    WARNING: Write operations modify raw disk data. Use with extreme caution.
    """

    def __init__(self, enable_aggressive_write=False, verbose=False):
        super().__init__(verbose=verbose)
        self.enable_aggressive_write = enable_aggressive_write

    # ------------------------------------------------------------------
    # Write handle helpers
    # ------------------------------------------------------------------

    def open_physical_drive_write(self, drive_number):
        """Open physical drive with write access — tries multiple modes."""
        drive_path = f"\\\\.\\PhysicalDrive{drive_number}"

        access_modes = [
            (GENERIC_WRITE, 0, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, 0),
        ]

        for access, share, flags in access_modes:
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path, access, share, None, OPEN_EXISTING, flags, None,
            )
            if handle != -1:
                return handle

        raise OSError(f"Cannot open PhysicalDrive{drive_number} for writing")

    def _open_volume_write(self, drive_letter):
        """Open volume with write access — tries multiple modes."""
        volume_path = f"\\\\.\\{drive_letter.upper()}:"

        access_modes = [
            (GENERIC_WRITE, 0, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH),
            (GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, 0),
        ]

        for access, share, flags in access_modes:
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, access, share, None, OPEN_EXISTING, flags, None,
            )
            if handle != -1:
                return handle

        raise OSError(f"Cannot open volume {drive_letter} for writing")

    # ------------------------------------------------------------------
    # Aggressive write helpers
    # ------------------------------------------------------------------

    def dismount_volume(self, drive_letter):
        """Dismount volume to enable raw write access."""
        try:
            volume_path = f"\\\\.\\{drive_letter.upper()}:"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path, GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None,
            )
            if handle == INVALID_HANDLE_VALUE:
                return False
            try:
                bytes_returned = wintypes.DWORD()
                return bool(ctypes.windll.kernel32.DeviceIoControl(
                    handle, FSCTL_DISMOUNT_VOLUME,
                    None, 0, None, 0, ctypes.byref(bytes_returned), None,
                ))
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False

    def take_disk_offline(self, drive_number):
        """Take physical disk offline to enable raw write access."""
        try:
            drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
            handle = ctypes.windll.kernel32.CreateFileW(
                drive_path, GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None,
            )
            if handle == INVALID_HANDLE_VALUE:
                return False
            try:
                IOCTL_DISK_OFFLINE = 0x00070020
                bytes_returned = wintypes.DWORD()
                return bool(ctypes.windll.kernel32.DeviceIoControl(
                    handle, IOCTL_DISK_OFFLINE,
                    None, 0, None, 0, ctypes.byref(bytes_returned), None,
                ))
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def _pad_to_sector(self, data):
        """Pad data to sector boundary."""
        remainder = len(data) % self.sector_size
        if remainder != 0:
            data = data + b'\x00' * (self.sector_size - remainder)
        return data

    def _write_at_offset(self, handle, byte_offset, data):
        """Seek + write + flush."""
        if not ctypes.windll.kernel32.SetFilePointerEx(
            handle, ctypes.c_longlong(byte_offset), None, 0
        ):
            error = ctypes.windll.kernel32.GetLastError()
            raise OSError(f"SetFilePointerEx failed: Error {error}")

        bytes_written = wintypes.DWORD(0)
        if not ctypes.windll.kernel32.WriteFile(
            handle, data, len(data), ctypes.byref(bytes_written), None
        ):
            error = ctypes.windll.kernel32.GetLastError()
            raise OSError(f"WriteFile failed: Error {error}")

        ctypes.windll.kernel32.FlushFileBuffers(handle)
        return bytes_written.value

    def write_lba_physical(self, drive_number, lba, data):
        """Write data to physical drive at specific LBA."""
        if self.enable_aggressive_write:
            self.take_disk_offline(drive_number)

        data = self._pad_to_sector(data)
        handle = self.open_physical_drive_write(drive_number)
        try:
            return self._write_at_offset(handle, lba * self.sector_size, data)
        finally:
            WindowsAPI.close_handle(handle)

    def write_lba_volume(self, drive_letter, lba_relative, data):
        """Write data to volume at relative LBA."""
        data = self._pad_to_sector(data)
        handle = self._open_volume_write(drive_letter)
        try:
            return self._write_at_offset(handle, lba_relative * self.sector_size, data)
        finally:
            WindowsAPI.close_handle(handle)
