"""
Reference Eliminator — Destroy directory entries, hard links, and security refs.

After a file's content and MFT record are destroyed, references may
still exist in:

* **Directory indexes ($I30)** — the parent folder's B-tree index.
* **Hard links** — additional MFT records pointing to the same data.
* **$Secure** — the shared security descriptor store (MFT record 9).

This module searches for and corrupts those references.

WARNING: Corrupting directory indexes and $Secure can cause widespread
file system damage beyond the target file.
"""
from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.analyzers.lba_reader import LBAReader
from ntfs_toolkit.dangerous.mft_destroyer import MFTDestroyer


class ReferenceEliminator:
    """Eliminate directory, hard-link, and security descriptor references."""

    def __init__(self, disk_writer: DiskWriter):
        self.disk_writer = disk_writer
        self.reader = LBAReader(disk_writer)
        self.mft_destroyer = MFTDestroyer(disk_writer)

    def eliminate_related_records(self, structure):
        """Run all reference elimination phases. Returns True if fully successful."""
        print("\nPhase 5: Related Records Elimination")
        dl = structure["drive_letter"]
        mft = structure["mft_record"]

        ok = True
        if not self._eliminate_directory_refs(dl, mft):
            ok = False
        if not self._eliminate_hard_links(dl, mft):
            ok = False
        if not self._eliminate_security_refs(dl, mft):
            ok = False
        return ok

    def _eliminate_directory_refs(self, drive_letter, mft_record):
        """Search common directory index areas for MFT record references."""
        print("  Eliminating directory references…")
        mft_bytes = mft_record.to_bytes(8, "little")
        pattern = b"\x00" * 512

        for idx_lba in (0x5000, 0x6000, 0x7000):
            try:
                data = self.reader.read_volume(drive_letter, idx_lba, 10240)
                for i in range(len(data) - 8):
                    if data[i : i + 8] == mft_bytes:
                        target = idx_lba + (i // 512)
                        try:
                            self.disk_writer.write_lba_volume(drive_letter, target, pattern)
                        except Exception:
                            pass
                return True
            except Exception:
                continue
        return False

    def _eliminate_hard_links(self, drive_letter, mft_record):
        """Scan MFT records for hard-link references and corrupt them."""
        print("  Eliminating hard links…")
        base = self.mft_destroyer.find_mft_base_lba(drive_letter)
        if base is None:
            return False

        mft_bytes = mft_record.to_bytes(8, "little")
        found = 0
        for rec in range(1000):
            lba = base + (rec * 2)
            try:
                data = self.reader.read_volume(drive_letter, lba, 1024)
                if mft_bytes in data:
                    pat = b"\x00" * 1024
                    self.disk_writer.write_lba_volume(drive_letter, lba, pat)
                    self.disk_writer.write_lba_volume(drive_letter, lba + 1, pat)
                    found += 1
            except Exception:
                continue
        print(f"    Corrupted {found} potential hard links")
        return True

    def _eliminate_security_refs(self, drive_letter, mft_record):
        """Corrupt the $Secure file (MFT record 9)."""
        print("  Eliminating security descriptors…")
        lba = self.mft_destroyer.find_mft_record_lba(drive_letter, 9)
        if lba is None:
            return False

        for pat in (b"\x00" * 1024, b"\xFF" * 1024):
            try:
                for off in range(5):
                    self.disk_writer.write_lba_volume(drive_letter, lba + off, pat)
            except Exception:
                return False
        return True
