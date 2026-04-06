"""
LBA Writer — Write raw data to specific LBA sectors.

WARNING: This module performs raw disk writes. Incorrect use can
corrupt file systems, destroy data, or render drives unbootable.

Provides safety confirmations by default — shows current content
before overwriting and requires explicit ``YES`` input.

Usage::

    from ntfs_toolkit.dangerous import LBAWriter

    writer = LBAWriter()
    writer.write_volume("D", lba=2048, data=b"test", confirm=True)
"""
from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.analyzers.lba_reader import LBAReader


class LBAWriter:
    """Write data to LBA on physical drives or volumes with safety prompts."""

    def __init__(self, enable_aggressive_write=False):
        self.disk_writer = DiskWriter(
            enable_aggressive_write=enable_aggressive_write,
        )
        self.reader = LBAReader(self.disk_writer)

    def write_physical(self, drive_number, lba, data, confirm=True):
        """Write to physical drive. Shows current content and asks for YES.

        Args:
            drive_number: Physical drive index (0, 1, …).
            lba:          Absolute sector number.
            data:         Bytes or string to write.
            confirm:      If True, prompt user before writing.

        Returns:
            Number of bytes written, or 0 if cancelled.
        """
        if not isinstance(data, bytes):
            data = data.encode("utf-8")

        if confirm:
            print(f"WARNING: Writing to PhysicalDrive{drive_number} LBA {lba}")
            print(f"  This will OVERWRITE {len(data)} bytes on the disk!")
            print(f"  Data: {data[:64]}")
            try:
                current = self.reader.read_physical(drive_number, lba, 512)
                print(f"\n  Current content: {current[:64].hex()}")
            except Exception:
                pass
            if input("\n  Type 'YES' to confirm: ") != "YES":
                print("  Cancelled.")
                return 0

        written = self.disk_writer.write_lba_physical(drive_number, lba, data)
        print(f"Wrote {written} bytes to PhysicalDrive{drive_number} LBA {lba}")
        return written

    def write_volume(self, drive_letter, lba, data, confirm=True):
        """Write to volume at relative LBA. Shows current content and asks for YES.

        Args:
            drive_letter: Volume letter without colon (e.g. ``"D"``).
            lba:          Sector number relative to volume start.
            data:         Bytes or string to write.
            confirm:      If True, prompt user before writing.

        Returns:
            Number of bytes written, or 0 if cancelled.
        """
        if not isinstance(data, bytes):
            data = data.encode("utf-8")

        if confirm:
            print(f"WARNING: Writing to Volume {drive_letter}: LBA {lba}")
            print(f"  This will OVERWRITE {len(data)} bytes!")
            print(f"  IMPORTANT: Close all files/programs using {drive_letter}: drive!")
            try:
                current = self.reader.read_volume(drive_letter, lba, 512)
                print(f"\n  Current content: {current[:64].hex()}")
            except Exception:
                pass
            input("\n  Press Enter when ready...")
            if input("  Type 'YES' to confirm: ") != "YES":
                print("  Cancelled.")
                return 0

        written = self.disk_writer.write_lba_volume(drive_letter, lba, data)
        print(f"Wrote {written} bytes to Volume {drive_letter}: LBA {lba}")
        return written
