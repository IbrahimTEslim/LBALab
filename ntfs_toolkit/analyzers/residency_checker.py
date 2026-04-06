"""
Residency Checker — Determine if an NTFS file is resident or non-resident.

NTFS stores very small files (typically < 700 bytes) *inside* the MFT
record itself — these are called **resident** files.  Larger files are
**non-resident**: their data lives in separate clusters on disk and the
MFT record only stores the extent map (VCN → LCN run list).

This distinction matters for forensics because resident file data can
only be recovered by parsing the MFT, while non-resident data can be
read directly from the disk clusters.

Usage::

    from ntfs_toolkit.analyzers import ResidencyChecker

    rc = ResidencyChecker()
    if rc.is_file_resident(r"C:\\tiny.txt"):
        print("Data lives inside the MFT record")
"""
from ntfs_toolkit.analyzers.extent_mapper import ExtentMapper


class ResidencyChecker:
    """Check whether a file's $DATA attribute is resident or non-resident."""

    def __init__(self, extent_mapper=None):
        self.mapper = extent_mapper or ExtentMapper()

    def is_file_resident(self, file_path):
        """Return ``True`` if the file is resident (no cluster allocations).

        Internally calls ``FSCTL_GET_RETRIEVAL_POINTERS`` — if the call
        fails with ``ERROR_INVALID_FUNCTION`` or ``ERROR_HANDLE_EOF`` the
        file has no extents, meaning its data is stored inside the MFT.
        """
        extents = self.mapper.get_file_extents(file_path)
        return extents is None
