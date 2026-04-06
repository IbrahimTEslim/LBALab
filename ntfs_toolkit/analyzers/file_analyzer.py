"""
File Analyzer — Query NTFS file metadata, volume geometry, and partition layout.

This module wraps several Windows APIs to extract information that NTFS
stores about every file:

* **MFT record number** — the file's unique index inside the Master File Table.
* **Volume geometry** — bytes-per-sector, bytes-per-cluster, MFT location, etc.
* **Partition offset** — where the volume starts on the physical disk (in LBAs).

Usage::

    from ntfs_toolkit.analyzers import FileAnalyzer

    fa   = FileAnalyzer()
    info = fa.get_file_info(r"C:\\Windows\\notepad.exe")
    print(info["mft_record_number"])
"""
import ctypes
from ctypes import wintypes

from ntfs_toolkit.core import DiskIO, WindowsAPI
from ntfs_toolkit.core.ntfs_structures import (
    BY_HANDLE_FILE_INFORMATION,
    NTFS_VOLUME_DATA_BUFFER,
    PARTITION_INFORMATION_EX,
)
from ntfs_toolkit.core.windows_api import (
    FSCTL_GET_NTFS_VOLUME_DATA,
    IOCTL_DISK_GET_PARTITION_INFO_EX,
    FILE_SHARE_READ,
    OPEN_EXISTING,
)


class FileAnalyzer:
    """Retrieve NTFS file, volume, and partition metadata."""

    def __init__(self, disk_io=None):
        self.disk_io = disk_io or DiskIO()

    # ------------------------------------------------------------------
    # File-level info
    # ------------------------------------------------------------------

    def get_file_info(self, file_path):
        """Return a dict with MFT record number, sequence, size, etc.

        Internally calls ``GetFileInformationByHandle`` and splits the
        64-bit file index into the 48-bit MFT record number and the
        16-bit sequence number that NTFS uses for reuse detection.
        """
        handle = self.disk_io.open_file(file_path)
        try:
            info = BY_HANDLE_FILE_INFORMATION()
            if not ctypes.windll.kernel32.GetFileInformationByHandle(
                handle, ctypes.byref(info)
            ):
                raise OSError("GetFileInformationByHandle failed")

            file_index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
            return {
                "file_index": file_index,
                "mft_record_number": file_index & 0xFFFFFFFFFFFF,
                "sequence_number": (file_index >> 48) & 0xFFFF,
                "volume_serial": info.dwVolumeSerialNumber,
                "file_size": (info.nFileSizeHigh << 32) | info.nFileSizeLow,
                "attributes": info.dwFileAttributes,
                "link_count": info.nNumberOfLinks,
            }
        finally:
            WindowsAPI.close_handle(handle)

    # ------------------------------------------------------------------
    # Volume-level info
    # ------------------------------------------------------------------

    def get_volume_info(self, drive_letter):
        """Return NTFS volume geometry via ``FSCTL_GET_NTFS_VOLUME_DATA``.

        Keys: bytes_per_sector, bytes_per_cluster, mft_start_lcn,
        mft_record_size, total_clusters, free_clusters, volume_serial.
        """
        handle = self.disk_io.open_volume(drive_letter)
        try:
            vol = NTFS_VOLUME_DATA_BUFFER()
            returned = wintypes.DWORD()
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, FSCTL_GET_NTFS_VOLUME_DATA, None, 0,
                ctypes.byref(vol), ctypes.sizeof(vol),
                ctypes.byref(returned), None,
            ):
                raise OSError("FSCTL_GET_NTFS_VOLUME_DATA failed")

            return {
                "volume_serial": vol.VolumeSerialNumber,
                "bytes_per_sector": vol.BytesPerSector,
                "bytes_per_cluster": vol.BytesPerCluster,
                "mft_start_lcn": vol.MftStartLcn,
                "mft_record_size": vol.BytesPerFileRecordSegment,
                "total_clusters": vol.TotalClusters,
                "free_clusters": vol.FreeClusters,
            }
        finally:
            WindowsAPI.close_handle(handle)

    # ------------------------------------------------------------------
    # Partition-level info
    # ------------------------------------------------------------------

    def get_partition_start_lba(self, drive_letter):
        """Return the LBA where this volume's partition begins on disk.

        Uses ``IOCTL_DISK_GET_PARTITION_INFO_EX`` and divides the byte
        offset by 512 (the standard sector size).
        """
        volume_path = f"\\\\.\\{drive_letter.upper()}:"
        handle = ctypes.windll.kernel32.CreateFileW(
            volume_path, 0, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None,
        )
        if handle == -1:
            raise OSError(f"Cannot open volume {drive_letter}")
        try:
            part = PARTITION_INFORMATION_EX()
            returned = wintypes.DWORD()
            if not ctypes.windll.kernel32.DeviceIoControl(
                handle, IOCTL_DISK_GET_PARTITION_INFO_EX, None, 0,
                ctypes.byref(part), ctypes.sizeof(part),
                ctypes.byref(returned), None,
            ):
                raise OSError("IOCTL_DISK_GET_PARTITION_INFO_EX failed")
            return part.StartingOffset // 512
        finally:
            WindowsAPI.close_handle(handle)

    def get_sectors_per_cluster(self, drive_letter):
        """Return ``(sectors_per_cluster, bytes_per_sector)`` tuple.

        Uses ``GetDiskFreeSpaceW`` which works without admin privileges.
        """
        spc = wintypes.DWORD()
        bps = wintypes.DWORD()
        fc = wintypes.DWORD()
        tc = wintypes.DWORD()
        if not ctypes.windll.kernel32.GetDiskFreeSpaceW(
            ctypes.c_wchar_p(f"{drive_letter}:\\\\"),
            ctypes.byref(spc), ctypes.byref(bps),
            ctypes.byref(fc), ctypes.byref(tc),
        ):
            raise OSError("GetDiskFreeSpaceW failed")
        return spc.value, bps.value
