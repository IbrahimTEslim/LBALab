"""
MFT Destroyer — Corrupt MFT records and their mirror copies.

Locates a file's MFT record by parsing the NTFS boot sector to find
the MFT base LBA, then overwrites the record (and its mirror) with
multiple corruption patterns.

WARNING: Corrupting MFT records can make files permanently unrecoverable
and may damage the file system.
"""
import os

from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.analyzers.lba_reader import LBAReader


class MFTDestroyer:
    """Locate and corrupt MFT records and their mirror copies."""

    def __init__(self, disk_writer: DiskWriter):
        self.disk_writer = disk_writer
        self.reader = LBAReader(disk_writer)

    # ------------------------------------------------------------------
    # MFT location helpers
    # ------------------------------------------------------------------

    def find_mft_base_lba(self, drive_letter):
        """Find the volume-relative LBA where the MFT begins.

        Reads the NTFS boot sector (LBA 0 of the volume) and extracts
        the MFT cluster number from offset 0x30 and sectors-per-cluster
        from offset 0x0D.

        Returns None if the boot sector cannot be parsed.
        """
        try:
            boot = self.reader.read_volume(drive_letter, 0, 512)
            if len(boot) >= 80:
                mft_cluster = int.from_bytes(boot[48:56], "little")
                spc = boot[13]
                return mft_cluster * spc
        except Exception:
            pass

        # Fallback: scan common locations for FILE signature
        for lba in (0x4000, 0x6000, 0x8000, 0x10000):
            try:
                data = self.reader.read_volume(drive_letter, lba, 512)
                if data[:4] == b"FILE":
                    return lba
            except Exception:
                continue
        return None

    def find_mft_record_lba(self, drive_letter, record_num):
        """Return the volume-relative LBA of MFT record *record_num*.

        Each MFT record is 1024 bytes = 2 sectors, so::

            record_lba = mft_base_lba + record_num * 2
        """
        base = self.find_mft_base_lba(drive_letter)
        if base is None:
            return None
        return base + (record_num * 2)

    def find_mft_mirror_record_lba(self, drive_letter, record_num):
        """Search the last 25 % of the volume for the MFT mirror.

        The $MFTMirr file is a partial backup of the first few MFT
        records, typically stored near the middle or end of the volume.
        Returns None if not found.
        """
        try:
            handle = self.reader.disk_io.open_volume(drive_letter)
            try:
                import ctypes
                size = ctypes.c_longlong(0)
                if not ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(size)):
                    return None
                total_sectors = size.value // 512
            finally:
                from ntfs_toolkit.core import WindowsAPI
                WindowsAPI.close_handle(handle)

            start = int(total_sectors * 0.75)
            for lba in range(start, total_sectors - 100, 1000):
                try:
                    data = self.reader.read_volume(drive_letter, lba, 512)
                    if data[:4] == b"FILE":
                        return lba + (record_num * 2)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Destruction
    # ------------------------------------------------------------------

    _CORRUPTION_PATTERNS = [
        b"\x00" * 1024,
        b"\xFF" * 1024,
        b"\xBA\xAD\xF0\x0D" * 256,
        b"\xDE\xAD\xBE\xEF" * 256,
        b"ERASED_FILE_RECORD" + b"\x00" * (1024 - 18),
    ]

    def corrupt_mft_record(self, structure):
        """Overwrite the target file's MFT record with corruption patterns.

        Returns True on success.
        """
        print("\nPhase 2: MFT Record Corruption")
        lba = self.find_mft_record_lba(structure["drive_letter"], structure["mft_record"])
        if lba is None:
            print(f"  Could not locate MFT record {structure['mft_record']}")
            return False

        return self._corrupt_at(structure["drive_letter"], lba, "MFT record")

    def destroy_mft_mirror(self, structure):
        """Overwrite the MFT mirror copy. Returns True on success."""
        print("\nPhase 3: MFT Mirror Destruction")
        lba = self.find_mft_mirror_record_lba(
            structure["drive_letter"], structure["mft_record"],
        )
        if lba is None:
            print("  MFT mirror not found (may not exist)")
            return True  # not a failure

        return self._corrupt_at(structure["drive_letter"], lba, "MFT mirror")

    def _corrupt_at(self, drive_letter, lba, label):
        """Apply all corruption patterns at *lba* and *lba+1*."""
        patterns = self._CORRUPTION_PATTERNS + [os.urandom(1024)]
        for i, pat in enumerate(patterns, 1):
            try:
                self.disk_writer.write_lba_volume(drive_letter, lba, pat)
                self.disk_writer.write_lba_volume(drive_letter, lba + 1, pat)
            except Exception as e:
                print(f"  {label} corruption pass {i} failed: {e}")
                return False
        print(f"  {label} destroyed ({len(patterns)} passes)")
        return True
