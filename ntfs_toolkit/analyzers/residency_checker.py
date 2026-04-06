"""
Residency Checker — Determine if an NTFS file is resident or non-resident.

NTFS stores very small files (typically < 700 bytes) *inside* the MFT
record itself — these are called **resident** files.  Larger files are
**non-resident**: their data lives in separate clusters on disk and the
MFT record only stores the extent map (VCN → LCN run list).

How NTFS tracks residency internally:

    Every $DATA attribute in the MFT record has a **non-resident flag**
    at byte offset 8 from the attribute start::

        $DATA attribute (type 0x80):
        Offset 0-3:   Type = 0x80
        Offset 4-7:   Attribute length
        Offset 8:     NON-RESIDENT FLAG   ← 0 = resident, 1 = non-resident
        Offset 9:     Name length
        Offset 10-11: Name offset

    When the flag is 0, the actual file content follows immediately
    inside the attribute body (within the MFT record).

    When the flag is 1, the attribute body contains a run list
    (VCN → LCN mapping) pointing to clusters on disk.

This module provides two methods:

1. **is_file_resident** (default, MFT-based): Reads the actual MFT
   record from disk, finds the $DATA attribute, and checks byte 8.
   This is the authoritative source — the same flag the OS reads.
   No ambiguity, no error-code interpretation.

2. **is_file_resident_api** (fast alternative): Calls
   ``FSCTL_GET_RETRIEVAL_POINTERS`` and interprets error codes.
   Faster and doesn't require admin, but can give false positives
   on non-NTFS volumes (FAT32, exFAT, network) or empty files
   because error 1/38 can mean things other than "resident."

Usage::

    from ntfs_toolkit.analyzers import ResidencyChecker

    rc = ResidencyChecker()

    # Default: reads the actual MFT flag (authoritative)
    rc.is_file_resident(r"C:\\tiny.txt")

    # Fast alternative: API-based (may be wrong on non-NTFS)
    rc.is_file_resident_api(r"C:\\tiny.txt")
"""
import os
from ntfs_toolkit.analyzers.extent_mapper import ExtentMapper
from ntfs_toolkit.analyzers.file_analyzer import FileAnalyzer
from ntfs_toolkit.analyzers.mft_parser import MFTParser


class ResidencyChecker:
    """Check whether a file's $DATA attribute is resident or non-resident."""

    def __init__(self, extent_mapper=None, disk_io=None):
        self.mapper = extent_mapper or ExtentMapper(disk_io)
        self._file_analyzer = None
        self._mft_parser = None
        self._disk_io = disk_io

    def is_file_resident(self, file_path):
        """Check residency by reading the MFT record (authoritative).

        Reads the file's MFT record from disk, walks the attribute
        chain to find $DATA (type 0x80), and checks byte 8:

        - ``0`` → resident (data is inside the MFT record)
        - ``1`` → non-resident (data is in clusters on disk)

        This is the same flag the NTFS driver checks internally.
        No error-code guessing, no ambiguity.

        Returns:
            ``True`` if resident, ``False`` if non-resident,
            ``None`` if no $DATA attribute was found.
        """
        if self._file_analyzer is None:
            self._file_analyzer = FileAnalyzer(self._disk_io)
        if self._mft_parser is None:
            self._mft_parser = MFTParser(self._disk_io)

        drive = os.path.splitdrive(file_path)[0].replace(":", "").upper()
        file_info = self._file_analyzer.get_file_info(file_path)
        vol = self._file_analyzer.get_volume_info(drive)

        raw = self._mft_parser.read_mft_record(
            drive, vol["mft_start_lcn"], vol["bytes_per_cluster"],
            vol["mft_record_size"], file_info["mft_record_number"],
        )

        attrs = self._mft_parser.parse_mft_attributes(raw)
        if not attrs:
            return None

        # Primary: check the first unnamed $DATA attribute
        for attr in attrs:
            if attr["is_unnamed"]:
                return attr["is_resident"]

        # Fallback: first $DATA attribute
        return attrs[0]["is_resident"]

    def is_file_resident_api(self, file_path):
        """Check residency via Windows API (fast but less reliable).

        Calls ``FSCTL_GET_RETRIEVAL_POINTERS`` on the file handle.
        If Windows returns error 1 or 38, we assume resident.

        WARNING: This can give false positives because error 1
        (ERROR_INVALID_FUNCTION) also fires on non-NTFS volumes
        (FAT32, exFAT, network drives), and error 38
        (ERROR_HANDLE_EOF) also fires on empty 0-byte files.
        Use ``is_file_resident()`` for authoritative results.

        Returns ``True`` if resident, ``False`` if non-resident.
        """
        extents = self.mapper.get_file_extents(file_path)
        return extents is None
