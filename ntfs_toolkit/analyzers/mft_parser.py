"""
MFT Parser — Read and parse NTFS Master File Table records.

Every file and directory on an NTFS volume has at least one MFT record
(1024 bytes by default).  The record starts with the signature ``FILE``
and contains a chain of *attributes* — $STANDARD_INFORMATION, $FILE_NAME,
$DATA, etc.

This module can:

* Read a raw MFT record from a live volume given its record number.
* Parse the 48-byte MFT record header (flags, sequence, link count …).
* Walk the attribute chain and extract $DATA attribute details
  (resident vs non-resident, named streams).

Usage::

    from ntfs_toolkit.analyzers import MFTParser, FileAnalyzer

    fa  = FileAnalyzer()
    vol = fa.get_volume_info("C")
    p   = MFTParser()
    raw = p.read_mft_record("C", vol["mft_start_lcn"],
                            vol["bytes_per_cluster"],
                            vol["mft_record_size"], record_index=5)
    hdr = p.parse_mft_header(raw)
"""
import ctypes
from ctypes import wintypes

from ntfs_toolkit.core import DiskIO, WindowsAPI, ATTR_DATA, ATTR_END


class MFTParser:
    """Parse raw MFT records from a live NTFS volume."""

    def __init__(self, disk_io=None):
        self.disk_io = disk_io or DiskIO()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_mft_record(self, drive_letter, mft_start_lcn,
                        bytes_per_cluster, mft_record_size, record_index):
        """Read a single MFT record by its index number.

        The byte offset on the volume is::

            (mft_start_lcn * bytes_per_cluster) + (record_index * mft_record_size)
        """
        handle = self.disk_io.open_volume(drive_letter)
        try:
            offset = (mft_start_lcn * bytes_per_cluster) + (record_index * mft_record_size)
            if not ctypes.windll.kernel32.SetFilePointerEx(
                handle, ctypes.c_longlong(offset), None, 0
            ):
                raise OSError("SetFilePointerEx failed")

            buf = ctypes.create_string_buffer(mft_record_size)
            read = wintypes.DWORD()
            if not ctypes.windll.kernel32.ReadFile(
                handle, buf, mft_record_size, ctypes.byref(read), None
            ):
                raise OSError("ReadFile failed")
            if read.value != mft_record_size:
                raise OSError(f"Short read: {read.value}/{mft_record_size} bytes")
            return buf.raw
        finally:
            WindowsAPI.close_handle(handle)

    # ------------------------------------------------------------------
    # Header parsing
    # ------------------------------------------------------------------

    def parse_mft_header(self, data):
        """Parse the 48-byte MFT record header and return a dict.

        Raises ``ValueError`` if the record is too small.
        """
        if len(data) < 48:
            raise ValueError(f"MFT record too small: {len(data)} bytes")

        sig = data[0:4]
        flags = int.from_bytes(data[22:24], "little")
        flag_names = []
        if flags & 0x0001:
            flag_names.append("IN_USE")
        if flags & 0x0002:
            flag_names.append("DIRECTORY")

        return {
            "signature": sig,
            "signature_valid": sig == b"FILE",
            "fixup_offset": int.from_bytes(data[4:6], "little"),
            "fixup_count": int.from_bytes(data[6:8], "little"),
            "lsn": int.from_bytes(data[8:16], "little"),
            "sequence_number": int.from_bytes(data[16:18], "little"),
            "link_count": int.from_bytes(data[18:20], "little"),
            "attrs_offset": int.from_bytes(data[20:22], "little"),
            "flags": flags,
            "flags_description": " | ".join(flag_names) or "NONE",
            "bytes_in_use": int.from_bytes(data[24:28], "little"),
            "bytes_allocated": int.from_bytes(data[28:32], "little"),
            "base_record": int.from_bytes(data[32:40], "little"),
            "next_attr_instance": int.from_bytes(data[40:42], "little"),
            "is_in_use": bool(flags & 0x0001),
            "is_directory": bool(flags & 0x0002),
        }

    # ------------------------------------------------------------------
    # Attribute walking
    # ------------------------------------------------------------------

    def parse_mft_attributes(self, data, debug=False):
        """Walk the attribute chain and return a list of $DATA attribute dicts.

        Each dict contains: offset, is_resident, length, stream_name, is_unnamed.

        BUG FIX: original used double-escaped ``b'\\\\x00…'`` for null-signature
        check which never matched actual null bytes.
        """
        if len(data) < 4 or data[:4] != b"FILE":
            if data[:4] == b"\x00\x00\x00\x00":
                raise ValueError("MFT record is free/unused")
            if data[:4] == b"BAAD":
                raise ValueError("MFT record is marked as bad")
            raise ValueError(f"Invalid MFT signature: {data[:4].hex().upper()}")

        if len(data) < 48:
            raise ValueError(f"MFT record too small: {len(data)} bytes")

        flags = int.from_bytes(data[22:24], "little")
        if not (flags & 0x0001):
            raise ValueError("MFT record not marked as in use")

        first_attr = int.from_bytes(data[0x14:0x16], "little")
        if first_attr >= len(data):
            raise ValueError("Invalid first attribute offset")

        pos = first_attr
        results = []
        count = 0

        while pos < len(data) - 8 and count < 50:
            attr_type = int.from_bytes(data[pos : pos + 4], "little")
            if attr_type == ATTR_END or attr_type == 0:
                break

            attr_len = int.from_bytes(data[pos + 4 : pos + 8], "little")
            if attr_len < 8 or attr_len > len(data) - pos or attr_len % 4 != 0:
                break

            if attr_type == ATTR_DATA and pos + 12 <= len(data):
                non_res = data[pos + 8]
                name_len = data[pos + 9]
                name_off = int.from_bytes(data[pos + 10 : pos + 12], "little")

                stream_name = ""
                if name_len > 0 and name_off > 0:
                    end = pos + name_off + name_len * 2
                    if end <= len(data):
                        try:
                            stream_name = data[pos + name_off : end].decode("utf-16le")
                        except Exception:
                            stream_name = f"<invalid_{name_len}>"

                results.append({
                    "offset": pos,
                    "is_resident": non_res == 0,
                    "length": attr_len,
                    "stream_name": stream_name,
                    "is_unnamed": name_len == 0,
                })

            pos += attr_len
            count += 1

        return results

    # ------------------------------------------------------------------
    # Hex dump
    # ------------------------------------------------------------------

    @staticmethod
    def hex_dump(data, offset=0, length=None):
        """Return a hex + ASCII dump (max *length* bytes, default 256)."""
        if length is None:
            length = min(len(data), 256)
        lines = []
        for i in range(0, length, 16):
            chunk = data[i : i + 16]
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{offset + i:08x}: {h:<47} | {a}")
        return "\n".join(lines)
