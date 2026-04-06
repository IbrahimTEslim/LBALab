"""
Comprehensive Analyzer — Full NTFS file analysis in one call.

Combines FileAnalyzer, ExtentMapper, MFTParser, and LBAReader to produce
a single dict that describes *everything* about a file's physical layout:

* MFT record number and its LBA on disk.
* Volume geometry (cluster size, partition offset, MFT location).
* Extent list with absolute LBAs and byte offsets.
* Residency status.

Usage::

    from ntfs_toolkit.analyzers import ComprehensiveAnalyzer

    ca     = ComprehensiveAnalyzer()
    result = ca.analyze(r"C:\\Windows\\notepad.exe")
    print(result["mft_record_lba"]["absolute"])
"""
import os

from ntfs_toolkit.core import DiskIO
from ntfs_toolkit.analyzers.file_analyzer import FileAnalyzer
from ntfs_toolkit.analyzers.extent_mapper import ExtentMapper
from ntfs_toolkit.analyzers.mft_parser import MFTParser
from ntfs_toolkit.analyzers.lba_reader import LBAReader


class ComprehensiveAnalyzer:
    """One-shot file analysis combining all read-only analyzers."""

    def __init__(self, disk_io=None):
        self.disk_io = disk_io or DiskIO()
        self.file_analyzer = FileAnalyzer(self.disk_io)
        self.extent_mapper = ExtentMapper(self.disk_io)
        self.mft_parser = MFTParser(self.disk_io)
        self.lba_reader = LBAReader(self.disk_io)

    def analyze(self, file_path):
        """Return a comprehensive dict describing the file's NTFS layout.

        Raises ``ValueError`` if the path does not exist or the drive
        letter cannot be determined.
        """
        if not os.path.exists(file_path):
            raise ValueError(f"Path does not exist: {file_path}")

        drive = os.path.splitdrive(file_path)[0].replace(":", "").upper()
        if not drive:
            raise ValueError("Could not determine drive letter")

        file_info = self.file_analyzer.get_file_info(file_path)
        vol = self.file_analyzer.get_volume_info(drive)
        part_lba = self.file_analyzer.get_partition_start_lba(drive)
        spc, bps = self.file_analyzer.get_sectors_per_cluster(drive)

        # MFT record location on disk
        mft_byte_start = vol["mft_start_lcn"] * vol["bytes_per_cluster"]
        rec_offset = file_info["mft_record_number"] * vol["mft_record_size"]
        total_offset = mft_byte_start + rec_offset
        mft_lba_rel = total_offset // bps
        mft_lba_abs = part_lba + mft_lba_rel

        result = {
            "file_path": file_path,
            "file_size": 0 if os.path.isdir(file_path) else os.path.getsize(file_path),
            "is_directory": os.path.isdir(file_path),
            "drive_letter": drive,
            "file_info": file_info,
            "volume_info": {
                "partition_start_lba": part_lba,
                "bytes_per_sector": bps,
                "bytes_per_cluster": vol["bytes_per_cluster"],
                "sectors_per_cluster": spc,
                "mft_start_lcn": vol["mft_start_lcn"],
                "mft_record_size": vol["mft_record_size"],
            },
            "mft_record_lba": {
                "relative": mft_lba_rel,
                "absolute": mft_lba_abs,
                "byte_offset": total_offset,
            },
            "is_resident": None,
            "extents": None,
        }

        # Extent mapping (files only)
        if not os.path.isdir(file_path):
            try:
                ext_data = self.extent_mapper.map_extents_to_lba(file_path)
                result["is_resident"] = ext_data["is_resident"]
                result["extents"] = ext_data["extents"]
            except Exception:
                pass

        return result

    def analyze_mft_record(self, drive_letter, record_number):
        """Read and parse a specific MFT record by number.

        Returns a dict with ``header``, ``data_attributes``, ``raw`` bytes,
        and the record's LBA location.
        """
        vol = self.file_analyzer.get_volume_info(drive_letter)
        part_lba = self.file_analyzer.get_partition_start_lba(drive_letter)

        mft_byte_start = vol["mft_start_lcn"] * vol["bytes_per_cluster"]
        rec_offset = record_number * vol["mft_record_size"]
        total_offset = mft_byte_start + rec_offset
        mft_lba_rel = total_offset // 512
        mft_lba_abs = part_lba + mft_lba_rel

        raw = self.mft_parser.read_mft_record(
            drive_letter, vol["mft_start_lcn"],
            vol["bytes_per_cluster"], vol["mft_record_size"], record_number,
        )

        result = {
            "record_number": record_number,
            "lba_relative": mft_lba_rel,
            "lba_absolute": mft_lba_abs,
            "byte_offset": total_offset,
            "raw": raw,
            "header": None,
            "data_attributes": None,
        }

        if raw[:4] == b"FILE":
            result["header"] = self.mft_parser.parse_mft_header(raw)
            try:
                result["data_attributes"] = self.mft_parser.parse_mft_attributes(raw)
            except ValueError:
                pass

        return result

    def verify_content(self, file_path, extent):
        """Read first 512 bytes from physical drive, volume, and file API.

        Returns a dict with the three byte samples and match booleans.
        Useful for verifying that LBA calculations are correct.
        """
        drive = os.path.splitdrive(file_path)[0].replace(":", "").upper()
        drive_num = self.disk_io.get_physical_drive_number(drive)

        phys = self.lba_reader.read_physical(drive_num, extent["lba_absolute"], 512)
        vol = self.lba_reader.read_volume(drive, extent["lba_relative"], 512)
        with open(file_path, "rb") as f:
            file_bytes = f.read(512)

        return {
            "physical": phys[:32],
            "volume": vol[:32],
            "file_api": file_bytes[:32],
            "physical_match": phys[:32] == file_bytes[:32],
            "volume_match": vol[:32] == file_bytes[:32],
        }
