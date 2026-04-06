"""
LBA Reader — Read raw sectors from physical drives or NTFS volumes.

LBA (Logical Block Address) is the sector-level addressing scheme used by
storage devices.  Each LBA maps to one sector (typically 512 bytes).

Usage::

    from ntfs_toolkit.analyzers import LBAReader

    reader = LBAReader()
    data   = reader.read_volume("C", lba=2048, size=512)
    print(reader.hex_dump(data))
"""
from ntfs_toolkit.core import DiskIO


class LBAReader:
    """Read raw sector content from physical drives or volumes."""

    def __init__(self, disk_io=None):
        self.disk_io = disk_io or DiskIO()

    def read_physical(self, drive_number, lba, size=512):
        """Read *size* bytes starting at absolute *lba* on PhysicalDrive.

        Args:
            drive_number: Physical drive index (0, 1, …).
            lba:          Absolute sector number on the physical disk.
            size:         How many bytes to read (rounded up to sector boundary).
        """
        return self.disk_io.read_lba_physical(drive_number, lba, size)

    def read_volume(self, drive_letter, lba, size=512):
        """Read *size* bytes starting at volume-relative *lba*.

        Args:
            drive_letter: Volume letter without colon (e.g. ``"C"``).
            lba:          Sector number relative to the start of the volume.
            size:         How many bytes to read.
        """
        return self.disk_io.read_lba_volume(drive_letter, lba, size)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hex_dump(data, offset=0):
        """Return a classic hex + ASCII dump string.

        Example output::

            00000000: 4d 5a 90 00 03 00 00 00 … | MZ......
        """
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{offset + i:08x}: {hex_part:<47} | {ascii_part}")
        return "\n".join(lines)
