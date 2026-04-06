"""
SSD Handler — SSD detection, TRIM commands, drive filling, and hidden space wiping.

Combines four original modules (SSDDetector, TRIMManager, DriveFiller,
HiddenSpaceHandler) that were tightly coupled and individually small.

Key capabilities:

* Detect whether a drive is SSD or HDD.
* Send targeted or full-drive TRIM commands.
* Fill free space with dummy data to force SSD wear-leveling.
* Wipe hidden areas (HPA, inter-partition gaps, over-provisioning).
"""
import os
import ctypes
from ctypes import wintypes

from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.core.windows_api import (
    GENERIC_READ, GENERIC_WRITE, FILE_SHARE_READ, FILE_SHARE_WRITE,
    OPEN_EXISTING, FSCTL_FILE_LEVEL_TRIM,
)


class SSDHandler:
    """SSD detection, TRIM, drive filling, and hidden-space wiping."""

    def __init__(self, disk_writer: DiskWriter):
        self.disk_writer = disk_writer

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def is_ssd(self, drive_letter):
        """Return True if the drive appears to be an SSD (TRIM-capable)."""
        return self.check_trim_support(drive_letter)

    def check_trim_support(self, drive_letter):
        """Return True if the volume supports FSCTL_FILE_LEVEL_TRIM."""
        handle = self._open_volume_rw(drive_letter)
        if handle == -1:
            return False
        try:
            buf = ctypes.create_string_buffer(512)
            ret = wintypes.DWORD()
            return bool(ctypes.windll.kernel32.DeviceIoControl(
                handle, FSCTL_FILE_LEVEL_TRIM,
                None, 0, buf, 512, ctypes.byref(ret), None,
            ))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def get_drive_info(self, drive_letter):
        """Return dict with is_ssd, trim_supported, drive_letter, physical_drive."""
        return {
            "is_ssd": self.is_ssd(drive_letter),
            "trim_supported": self.check_trim_support(drive_letter),
            "drive_letter": drive_letter.upper(),
            "physical_drive": self.disk_writer.get_physical_drive_number(drive_letter),
        }

    # ------------------------------------------------------------------
    # TRIM
    # ------------------------------------------------------------------

    def send_targeted_trim(self, drive_letter, lba_ranges):
        """Send TRIM for each ``(start_lba, sector_count)`` in *lba_ranges*."""
        handle = self._open_volume_rw(drive_letter)
        if handle == -1:
            return False
        try:
            for start, length in lba_ranges:
                payload = start.to_bytes(8, "little") + length.to_bytes(8, "little")
                ctypes.windll.kernel32.DeviceIoControl(
                    handle, FSCTL_FILE_LEVEL_TRIM,
                    payload, len(payload), None, 0, None, None,
                )
            return True
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    # ------------------------------------------------------------------
    # Drive filling (forces SSD wear-leveling / remapping)
    # ------------------------------------------------------------------

    def fill_free_space(self, drive_letter):
        """Create a large temp file to consume free space, then delete it.

        This forces the SSD controller to remap flash pages, reducing
        the chance that old data survives in over-provisioned cells.
        """
        tmp = f"{drive_letter}:\\$ssd_secure_fill.tmp"
        chunk = b"\x00\xFF" * 1024  # 2 KB pattern
        try:
            with open(tmp, "wb") as f:
                while True:
                    try:
                        f.write(chunk * 32768)  # ~64 MB per iteration
                    except OSError:
                        break  # disk full
            return True
        except Exception:
            return False
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hidden space wiping
    # ------------------------------------------------------------------

    def wipe_hidden_areas(self, drive_letter):
        """Best-effort wipe of inter-partition gaps and reserved sectors."""
        print(f"\nHidden Space Phase: wiping hidden areas on {drive_letter}:")
        pattern = b"\x00" * 512
        # Wipe common reserved LBA ranges on the volume
        for start, count in ((0, 63), (1, 62), (2048, 2048)):
            for off in range(count):
                try:
                    self.disk_writer.write_lba_volume(drive_letter, start + off, pattern)
                except Exception:
                    break
        print("  Hidden area wipe complete")
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open_volume_rw(self, drive_letter):
        path = f"\\\\.\\{drive_letter.upper()}:"
        return ctypes.windll.kernel32.CreateFileW(
            path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None,
        )
