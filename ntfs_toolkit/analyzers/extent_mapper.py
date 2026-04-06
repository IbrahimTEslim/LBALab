"""
Extent Mapper — Resolve the physical disk location of any NTFS file.

NTFS stores non-resident file data in *extents* — contiguous runs of
clusters on the volume.  Each extent is described by a VCN→LCN mapping:

* **VCN** (Virtual Cluster Number) — logical cluster index within the file.
* **LCN** (Logical Cluster Number) — physical cluster on the NTFS volume.
* **LBA** (Logical Block Address)  — absolute sector on the physical disk,
  computed as ``partition_start_lba + lcn * sectors_per_cluster``.

Usage::

    from ntfs_toolkit.analyzers import ExtentMapper

    mapper  = ExtentMapper()
    result  = mapper.map_extents_to_lba(r"C:\\Windows\\notepad.exe")
    for ext in result["extents"]:
        print(ext["lba_absolute"], ext["size_bytes"])
"""
import os
import ctypes
from ctypes import wintypes

from ntfs_toolkit.core import DiskIO, WindowsAPI
from ntfs_toolkit.core.ntfs_structures import STARTING_VCN_INPUT_BUFFER
from ntfs_toolkit.core.windows_api import FSCTL_GET_RETRIEVAL_POINTERS
from ntfs_toolkit.analyzers.file_analyzer import FileAnalyzer


class ExtentMapper:
    """Map file extents to physical disk locations (VCN → LCN → LBA)."""

    def __init__(self, disk_io=None):
        self.disk_io = disk_io or DiskIO()
        self.analyzer = FileAnalyzer(self.disk_io)

    def get_file_extents(self, file_path):
        """Return list of ``(start_vcn, next_vcn, lcn)`` tuples, or None if resident.

        A return value of ``None`` means the file's $DATA attribute is
        *resident* — its content lives inside the MFT record itself and
        no clusters are allocated on disk.

        Sparse extents are indicated by ``lcn == -1``.
        """
        handle = self.disk_io.open_file(file_path)
        try:
            inp = STARTING_VCN_INPUT_BUFFER(0)
            out_size = 8192
            out = ctypes.create_string_buffer(out_size)
            returned = wintypes.DWORD()

            ok = ctypes.windll.kernel32.DeviceIoControl(
                handle, FSCTL_GET_RETRIEVAL_POINTERS,
                ctypes.byref(inp), ctypes.sizeof(inp),
                out, out_size, ctypes.byref(returned), None,
            )

            if not ok:
                err = ctypes.GetLastError()
                # Error 1  = ERROR_INVALID_FUNCTION  → resident file
                # Error 38 = ERROR_HANDLE_EOF         → resident file
                if err in (1, 38):
                    return None
                raise OSError(f"FSCTL_GET_RETRIEVAL_POINTERS failed: error {err}")

            if returned.value < 16:
                return None

            extent_count = int.from_bytes(out[0:4], "little")
            current_vcn = int.from_bytes(out[8:16], "little")

            extents = []
            for i in range(extent_count):
                off = 16 + i * 16
                if off + 16 > returned.value:
                    break

                next_vcn = int.from_bytes(out[off : off + 8], "little")
                lcn_raw = out[off + 8 : off + 16]

                # Sparse extents are signalled by an all-0xFF LCN
                # BUG FIX: original used double-escaped b'\\xff' which never matched
                if lcn_raw == b"\xff" * 8:
                    lcn = -1
                else:
                    lcn = int.from_bytes(lcn_raw, "little", signed=True)
                    if lcn < 0:
                        lcn = -1

                extents.append((current_vcn, next_vcn, lcn))
                current_vcn = next_vcn

            return extents
        finally:
            WindowsAPI.close_handle(handle)

    def map_extents_to_lba(self, file_path):
        """Return a dict describing every extent with its absolute LBA.

        Returns::

            {
                "is_resident": bool,
                "extents": [ { "start_vcn", "next_vcn", "cluster_count",
                               "lcn", "lba_relative", "lba_absolute",
                               "byte_offset", "size_bytes", "type" }, … ],
                "partition_lba": int,
                "sectors_per_cluster": int,
            }
        """
        drive_letter = os.path.splitdrive(file_path)[0].replace(":", "")
        vol = self.analyzer.get_volume_info(drive_letter)
        partition_lba = self.analyzer.get_partition_start_lba(drive_letter)
        spc, bps = self.analyzer.get_sectors_per_cluster(drive_letter)

        extents = self.get_file_extents(file_path)
        if extents is None:
            return {"is_resident": True, "extents": []}

        mappings = []
        for start_vcn, next_vcn, lcn in extents:
            clusters = next_vcn - start_vcn
            if lcn == -1:
                mappings.append({
                    "start_vcn": start_vcn, "next_vcn": next_vcn,
                    "cluster_count": clusters, "type": "sparse",
                })
            else:
                rel_lba = lcn * spc
                abs_lba = partition_lba + rel_lba
                mappings.append({
                    "start_vcn": start_vcn, "next_vcn": next_vcn,
                    "cluster_count": clusters, "lcn": lcn,
                    "lba_relative": rel_lba, "lba_absolute": abs_lba,
                    "byte_offset": abs_lba * bps,
                    "size_bytes": clusters * vol["bytes_per_cluster"],
                    "type": "allocated",
                })

        return {
            "is_resident": False, "extents": mappings,
            "partition_lba": partition_lba, "sectors_per_cluster": spc,
        }
