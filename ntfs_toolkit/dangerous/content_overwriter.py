"""
Content Overwriter — Multi-pass file content destruction.

Overwrites file data sectors with multiple patterns (zeros, ones,
alternating bits, random data) to make recovery difficult.

This module operates on a ``structure`` dict produced by
:meth:`SecureDeleter.analyze_file_structure`.
"""
import os
import time

from ntfs_toolkit.core.disk_writer import DiskWriter

# Standard overwrite patterns (512 bytes each)
STANDARD_PATTERNS = [
    b"\x00" * 512,          # All zeros
    b"\xFF" * 512,          # All ones
    b"\xAA" * 512,          # Alternating 10101010
    b"\x55" * 512,          # Alternating 01010101
    b"\x00\xFF" * 256,      # 00FF repeating
    b"\xFF\x00" * 256,      # FF00 repeating
]

# Additional patterns for extra passes
SECURE_PATTERNS = [
    bytes([i % 256 for i in range(512)]),
    bytes([255 - (i % 256) for i in range(512)]),
    bytes([(i * 3) % 256 for i in range(512)]),
    bytes([(i * 7 + 13) % 256 for i in range(512)]),
]


class ContentOverwriter:
    """Multi-pass content overwriting for file data sectors."""

    def __init__(self, disk_writer: DiskWriter):
        self.disk_writer = disk_writer

    def overwrite_file_content(self, structure, passes=7):
        """Overwrite every sector of the file with *passes* different patterns.

        Args:
            structure: Dict with keys ``is_resident``, ``drive_letter``,
                       ``lba_ranges`` (list of ``(start_lba, sector_count)``).
            passes:    Number of overwrite passes (default 7).

        Returns:
            True if all sectors were overwritten successfully.
        """
        print(f"\nPhase 1: Content Overwriting ({passes} passes)")

        if structure["is_resident"]:
            print("  File is resident — content is in MFT record only")
            return True

        total_sectors = sum(length for _, length in structure["lba_ranges"])
        print(f"  Total sectors to overwrite: {total_sectors:,}")

        success = True
        for pass_num in range(passes):
            pattern = self._pattern_for_pass(pass_num)
            print(f"  Pass {pass_num + 1}/{passes}  pattern: {pattern[:8].hex()}…")

            written = 0
            for start_lba, length in structure["lba_ranges"]:
                for offset in range(length):
                    try:
                        self.disk_writer.write_lba_volume(
                            structure["drive_letter"], start_lba + offset, pattern,
                        )
                        written += 1
                    except Exception as e:
                        print(f"    Failed LBA {start_lba + offset}: {e}")
                        success = False

            print(f"    Pass {pass_num + 1} done: {written:,}/{total_sectors:,} sectors")
            time.sleep(0.1)  # brief pause between passes

        return success

    @staticmethod
    def _pattern_for_pass(pass_num):
        """Select the byte pattern for a given pass number."""
        if pass_num < len(STANDARD_PATTERNS):
            return STANDARD_PATTERNS[pass_num]
        extra = (pass_num - len(STANDARD_PATTERNS)) % (len(SECURE_PATTERNS) + 1)
        if extra == len(SECURE_PATTERNS):
            return os.urandom(512)
        return SECURE_PATTERNS[extra]
