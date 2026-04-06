"""
Metadata Wiper — Destroy traces in NTFS system journals.

NTFS keeps several metadata logs that record file operations:

* **$UsnJrnl** (USN Journal) — change journal tracking every file modification.
* **$LogFile** — transaction log for crash recovery.

This module searches those areas for references to a target MFT record
number and overwrites them.

WARNING: Corrupting system journals may cause NTFS consistency errors
and trigger chkdsk on next boot.
"""
from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.analyzers.lba_reader import LBAReader
from ntfs_toolkit.dangerous.mft_destroyer import MFTDestroyer


class MetadataWiper:
    """Wipe file traces from NTFS system journals."""

    def __init__(self, disk_writer: DiskWriter):
        self.disk_writer = disk_writer
        self.reader = LBAReader(disk_writer)
        self.mft_destroyer = MFTDestroyer(disk_writer)

    def wipe_metadata_traces(self, structure):
        """Run all metadata wiping phases. Returns True if fully successful."""
        print("\nPhase 4: Metadata Wiping")
        dl = structure["drive_letter"]
        mft = structure["mft_record"]

        ok = True
        if not self._wipe_usn_journal(dl, mft):
            ok = False
        if not self._wipe_logfile(dl, mft):
            ok = False
        if not self._wipe_usnjrnl_mft(dl):
            ok = False
        return ok

    def _wipe_usn_journal(self, drive_letter, mft_record):
        """Zero out common USN journal locations."""
        print("  Wiping USN journal entries…")
        pattern = b"\x00" * 512
        for usn_lba in (0x100000, 0x200000, 0x400000):
            try:
                for off in range(1000):
                    try:
                        self.disk_writer.write_lba_volume(drive_letter, usn_lba + off, pattern)
                    except Exception:
                        continue
                print(f"    Wiped USN area at LBA {usn_lba:,}")
                return True
            except Exception:
                continue
        return False

    def _wipe_logfile(self, drive_letter, mft_record):
        """Search $LogFile for MFT record references and corrupt them."""
        print("  Wiping $LogFile entries…")
        mft_bytes = mft_record.to_bytes(8, "little")
        pattern = b"\xFF" * 512

        for log_lba in (0x1000, 0x2000, 0x3000):
            try:
                data = self.reader.read_volume(drive_letter, log_lba, 5120)
                for i in range(len(data) - 8):
                    if data[i : i + 8] == mft_bytes:
                        target = log_lba + (i // 512)
                        try:
                            self.disk_writer.write_lba_volume(drive_letter, target, pattern)
                        except Exception:
                            pass
                return True
            except Exception:
                continue
        return False

    def _wipe_usnjrnl_mft(self, drive_letter):
        """Corrupt the $UsnJrnl MFT record itself (record 25)."""
        print("  Wiping $UsnJrnl MFT record…")
        lba = self.mft_destroyer.find_mft_record_lba(drive_letter, 25)
        if lba is None:
            return False
        for pat in (b"\x00" * 1024, b"\xFF" * 1024):
            try:
                self.disk_writer.write_lba_volume(drive_letter, lba, pat)
                self.disk_writer.write_lba_volume(drive_letter, lba + 1, pat)
            except Exception:
                return False
        return True
