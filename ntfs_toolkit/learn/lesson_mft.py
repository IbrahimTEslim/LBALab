"""
Lesson 3: MFT Records
======================

The **Master File Table (MFT)** is the heart of NTFS.  Every file and
directory on the volume has at least one MFT record — a 1024-byte
structure that stores:

- The file's name, timestamps, permissions ($STANDARD_INFORMATION)
- The file's name again in a different format ($FILE_NAME)
- The file's actual data or a pointer to it ($DATA)
- And more attributes...

MFT Record Layout (1024 bytes):
    ┌────────────────────────────────────────────┐
    │ Header (first 48 bytes)                    │
    │   Signature: "FILE" (4 bytes)              │
    │   Fixup offset & count                     │
    │   Log Sequence Number (LSN)                │
    │   Sequence number (reuse counter)          │
    │   Link count (hard links)                  │
    │   First attribute offset                   │
    │   Flags: IN_USE, DIRECTORY                 │
    │   Bytes used / allocated                   │
    ├────────────────────────────────────────────┤
    │ Attribute 1: $STANDARD_INFORMATION (0x10)  │
    │ Attribute 2: $FILE_NAME (0x30)             │
    │ Attribute 3: $DATA (0x80)                  │
    │ ...more attributes...                      │
    │ End marker: 0xFFFFFFFF                     │
    ├────────────────────────────────────────────┤
    │ Unused space (padding to 1024 bytes)       │
    └────────────────────────────────────────────┘

Special MFT records (always present):
    Record 0:  $MFT itself (the MFT's own file entry)
    Record 1:  $MFTMirr (mirror of first 4 records)
    Record 2:  $LogFile (transaction journal)
    Record 3:  $Volume (volume name and version)
    Record 4:  $AttrDef (attribute definitions)
    Record 5:  . (root directory)
    Record 6:  $Bitmap (cluster allocation bitmap)
    Record 7:  $Boot (boot sector backup)
    Record 8:  $BadClus (bad cluster list)
    Record 9:  $Secure (security descriptors)
    Record 10: $UpCase (uppercase mapping table)
    Record 11: $Extend (extensions directory)
"""
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, decode_reveal, hex_reveal,
    flash_result,
)
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer


def run(drive_letter="C", animate=False):
    console.print()
    typewriter("  Lesson 3: MFT Records", style="bold magenta",
               enabled=animate)
    console.rule("[bold magenta]Lesson 3: MFT Records[/]")

    # --- What is the MFT ---
    intro = [
        "",
        "  The [bold]MFT (Master File Table)[/] is a database of every file.",
        "  Each file gets a [bold]1024-byte record[/] with a unique number.",
        "",
        "  The first 12 records are reserved for system files:",
        "",
        "  [dim] #0[/]  $MFT        — the MFT's own entry",
        "  [dim] #1[/]  $MFTMirr    — backup of records 0-3",
        "  [dim] #2[/]  $LogFile    — transaction journal",
        "  [dim] #3[/]  $Volume     — volume name & version",
        "  [dim] #5[/]  [bold]. (root)[/]   — the root directory",
        "  [dim] #6[/]  $Bitmap     — which clusters are in use",
        "  [dim] #9[/]  $Secure     — security descriptors",
        "",
        "  Every record starts with the signature [bold]FILE[/] (hex: 46 49 4c 45)",
        "  If you see [bold]BAAD[/] instead, the record is corrupted.",
        "",
    ]
    panel_build(intro, title="What is the MFT?", style="magenta",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(intro), title="What is the MFT?",
                            border_style="magenta"))

    # --- Read a real MFT record ---
    ca = ComprehensiveAnalyzer()
    console.print(f"\n  [bold]Reading MFT Record #5 (root directory)"
                  f" from {drive_letter}:...[/]\n")

    result = ca.analyze_mft_record(drive_letter, 5)
    raw = result["raw"]

    # Show first 64 bytes of raw MFT record
    hex_reveal(raw[:64], title="MFT Record #5 — Raw Bytes (first 64)",
               enabled=animate)
    if not animate:
        from ntfs_toolkit.explorer.display import show_hex_panel
        show_hex_panel(raw[:64], title="MFT Record #5 — Raw Bytes")

    # --- Parse the header ---
    hdr = result.get("header")
    if hdr:
        _show_header_breakdown(hdr, raw, animate)

    # --- Show $DATA attributes ---
    attrs = result.get("data_attributes")
    if attrs:
        _show_data_attributes(attrs, animate)

    # --- Explain how to find any file's MFT record ---
    find_info = [
        "",
        "  [bold yellow]How to find any file's MFT record:[/]",
        "",
        "  1. Open the file with CreateFileW (Windows API)",
        "  2. Call GetFileInformationByHandle",
        "  3. The 64-bit file index contains:",
        "     • Bits 0-47:  MFT record number",
        "     • Bits 48-63: Sequence number (reuse counter)",
        "",
        "  The [bold]sequence number[/] increments each time the record",
        "  is reused for a different file. This prevents stale references.",
        "",
        f"  MFT record byte offset on volume:",
        f"  [bold]offset = MFT_start_LCN x cluster_size + record# x 1024[/]",
        "",
    ]
    panel_build(find_info, title="Finding MFT Records", style="yellow",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(find_info),
                            title="Finding MFT Records",
                            border_style="yellow"))

    # --- Takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • Every file has a 1024-byte MFT record with signature FILE",
        "  • Records 0-11 are system files ($MFT, $LogFile, root dir, etc.)",
        "  • The header has flags (IN_USE, DIRECTORY), sequence, link count",
        "  • Attributes are chained inside the record (0x10, 0x30, 0x80...)",
        "  • $DATA (0x80) holds the file content or points to clusters",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))


def _show_header_breakdown(hdr, raw, animate):
    """Show MFT header fields with byte offsets."""
    fields = [
        "",
        f"  [dim]Offset 0-3:[/]   Signature      ="
        f" [bold]{'FILE' if hdr['signature_valid'] else 'INVALID'}[/]"
        f"  {'[green]✓[/]' if hdr['signature_valid'] else '[red]✗[/]'}",
        f"  [dim]Offset 4-5:[/]   Fixup offset   = {hdr['fixup_offset']}",
        f"  [dim]Offset 6-7:[/]   Fixup count    = {hdr['fixup_count']}",
        f"  [dim]Offset 8-15:[/]  LSN            = {hdr['lsn']:,}",
        f"  [dim]Offset 16-17:[/] Sequence       = [bold]{hdr['sequence_number']}[/]",
        f"  [dim]Offset 18-19:[/] Link count     = {hdr['link_count']}",
        f"  [dim]Offset 20-21:[/] First attr     = offset {hdr['attrs_offset']}",
        f"  [dim]Offset 22-23:[/] Flags          ="
        f" 0x{hdr['flags']:04x} ([bold]{hdr['flags_description']}[/])",
        f"  [dim]Offset 24-27:[/] Bytes used     = {hdr['bytes_in_use']}",
        f"  [dim]Offset 28-31:[/] Bytes allocated= {hdr['bytes_allocated']}",
        "",
    ]
    panel_build(fields, title="MFT Header Breakdown", style="cyan",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(fields),
                            title="MFT Header Breakdown",
                            border_style="cyan"))
    if hdr["signature_valid"]:
        flash_result("  FILE signature valid ✓", enabled=animate)


def _show_data_attributes(attrs, animate):
    """Show $DATA attributes found in the record."""
    t = Table(title="$DATA Attributes Found")
    t.add_column("#", style="dim")
    t.add_column("Offset", justify="right")
    t.add_column("Status")
    t.add_column("Size", justify="right")
    t.add_column("Stream Name")
    for i, a in enumerate(attrs, 1):
        st = "[green]RESIDENT[/]" if a["is_resident"] \
            else "[yellow]NON-RESIDENT[/]"
        nm = f"'{a['stream_name']}'" if a["stream_name"] else "(unnamed)"
        t.add_row(str(i), str(a["offset"]), st,
                  f"{a['length']} bytes", nm)
    console.print(t)
