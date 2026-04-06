"""Display — Rich panels with cinematic effects for NTFS analysis."""
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, hex_reveal, decode_reveal, panel_build,
    typewriter, scan_line, flash_result,
)


def _panel(text, title, style, animate, effect="build"):
    """Show a panel — with effect if animated, plain if not."""
    if animate:
        if effect == "build":
            lines = text.split("\n") if isinstance(text, str) else text
            panel_build(lines, title=title, style=style, enabled=True)
        elif effect == "decode":
            decode_reveal(text, title=title, style=style, enabled=True)
        elif effect == "scan":
            scan_line(text, title=title, style=style, enabled=True)
    else:
        body = text if isinstance(text, str) else "\n".join(text)
        console.print(Panel(body, title=title, border_style=style))


def show_file_analysis(result, animate=False):
    """Render a ComprehensiveAnalyzer.analyze() result with effects."""
    fi, vi, ml = result["file_info"], result["volume_info"], result["mft_record_lba"]
    is_dir = result["is_directory"]

    console.print()
    typewriter(f"  NTFS Analysis: {result['file_path']}", enabled=animate)
    console.rule(f"[bold cyan]NTFS Analysis: {result['file_path']}[/]")

    # File Info
    info = [f"  Type:  {'Directory' if is_dir else 'File'}"]
    if not is_dir:
        info.append(f"  Size:  {result['file_size']:,} bytes")
    info.append(f"  Drive: {result['drive_letter']}:")
    _panel(info, "File Info", "blue", animate)

    # MFT Record — decode effect
    mft = (f"  Record #       {fi['mft_record_number']:,}\n"
           f"  Sequence       {fi['sequence_number']}\n"
           f"  LBA (absolute) {ml['absolute']:,}\n"
           f"  LBA (relative) {ml['relative']:,}\n"
           f"  Byte offset    {ml['byte_offset']:,}")
    _panel(mft, "MFT Record", "green", animate, effect="decode")

    # Volume Geometry
    vol = [f"  Partition start  {vi['partition_start_lba']:,}",
           f"  Bytes/sector     {vi['bytes_per_sector']}",
           f"  Bytes/cluster    {vi['bytes_per_cluster']:,}",
           f"  Sectors/cluster  {vi['sectors_per_cluster']}",
           f"  MFT start LCN   {vi['mft_start_lcn']:,}",
           f"  MFT record size  {vi['mft_record_size']} bytes"]
    _panel(vol, "Volume Geometry", "yellow", animate)

    if not is_dir:
        _show_extents(result, animate)
    _show_lba_calc(fi, vi, ml, animate)
    console.print()


def _show_extents(result, animate):
    if result["is_resident"]:
        _panel("RESIDENT — data inside MFT record",
               "Data Status", "green", animate, effect="scan")
        return
    _panel("NON-RESIDENT — data in disk clusters",
           "Data Status", "yellow", animate, effect="scan")
    if not result.get("extents"):
        return
    t = Table(title="Extents (VCN -> LCN -> LBA)")
    t.add_column("#", style="dim", justify="right")
    t.add_column("VCN Range")
    t.add_column("Clusters", justify="right")
    t.add_column("LCN", justify="right")
    t.add_column("LBA (abs)", justify="right", style="bold")
    t.add_column("Size", justify="right")
    t.add_column("Type")
    for i, ext in enumerate(result["extents"], 1):
        vcn = f"{ext['start_vcn']}-{ext['next_vcn'] - 1}"
        cl = f"{ext['cluster_count']:,}"
        if ext["type"] == "sparse":
            t.add_row(str(i), vcn, cl, "-", "-", "-", "[red]SPARSE[/]")
        else:
            t.add_row(str(i), vcn, cl, f"{ext['lcn']:,}",
                      f"{ext['lba_absolute']:,}", _fmt_size(ext["size_bytes"]),
                      "[green]allocated[/]")
    console.print(t)


def _show_lba_calc(fi, vi, ml, animate):
    L, B = vi["mft_start_lcn"], vi["bytes_per_cluster"]
    R, S = fi["mft_record_number"], vi["mft_record_size"]
    bps, P = vi["bytes_per_sector"], vi["partition_start_lba"]
    mb, ro = L * B, R * S
    tot = mb + ro
    lines = [
        f"  1. MFT starts at LCN {L:,}",
        f"  2. MFT byte offset = {L:,} x {B:,} = {mb:,}",
        f"  3. Record {R:,} offset = {R:,} x {S:,} = {ro:,}",
        f"  4. Total = {mb:,} + {ro:,} = {tot:,}",
        f"  5. Relative LBA = {tot:,} / {bps} = {ml['relative']:,}",
        f"  6. Absolute LBA = {P:,} + {ml['relative']:,} = {ml['absolute']:,}",
    ]
    _panel(lines, "LBA Calculation", "cyan", animate)


def show_mft_record(record_data, animate=False):
    """Render MFT record with decode effect."""
    console.print()
    typewriter(f"  MFT Record #{record_data['record_number']}", enabled=animate)
    console.rule(f"[bold cyan]MFT Record #{record_data['record_number']}[/]")

    loc = (f"  LBA (abs): {record_data['lba_absolute']:,}  "
           f"LBA (rel): {record_data['lba_relative']:,}  "
           f"Offset: {record_data['byte_offset']:,}")
    _panel(loc, "Location", "green", animate, effect="decode")

    hdr = record_data.get("header")
    if hdr and hdr["signature_valid"]:
        h = [f"  Signature: FILE  ✓",
             f"  Flags:     0x{hdr['flags']:04x} ({hdr['flags_description']})",
             f"  Sequence:  {hdr['sequence_number']}    Links: {hdr['link_count']}",
             f"  Used:      {hdr['bytes_in_use']} / {hdr['bytes_allocated']} bytes"]
        _panel(h, "Header", "yellow", animate)
        flash_result("  FILE signature valid ✓", enabled=animate)
    else:
        console.print(Panel("[red]Invalid MFT signature[/]", border_style="red"))

    attrs = record_data.get("data_attributes")
    if attrs:
        t = Table(title="$DATA Attributes")
        t.add_column("#", style="dim")
        t.add_column("Status")
        t.add_column("Stream")
        for i, a in enumerate(attrs, 1):
            st = "[green]RESIDENT[/]" if a["is_resident"] else "[yellow]NON-RESIDENT[/]"
            nm = f"'{a['stream_name']}'" if a["stream_name"] else "(unnamed)"
            t.add_row(str(i), st, nm)
        console.print(t)
    console.print()


def show_hex_panel(data, title="Hex Dump", offset=0, animate=False):
    """Hex dump with streaming byte reveal effect."""
    if animate:
        hex_reveal(data, title=title, offset=offset, enabled=True)
    else:
        bpr = 16 if console.width >= 100 else 8
        lines = []
        for i in range(0, min(len(data), 256), bpr):
            chunk = data[i:i + bpr]
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"  [dim]{offset+i:08x}:[/] {h:<{bpr*3-1}} [dim]|[/] {a}")
        console.print(Panel("\n".join(lines), title=title, border_style="blue"))


def show_residency(file_path, is_resident, file_size):
    """Residency check result."""
    s = "RESIDENT" if is_resident else "NON-RESIDENT"
    c = "green" if is_resident else "yellow"
    t = f"  File: {file_path}\n  Size: {file_size:,} bytes\n  Status: [{c}]{s}[/]"
    if is_resident:
        t += "\n\n  [dim]Data inside MFT record — no clusters.[/]"
    else:
        t += "\n\n  [dim]Data in disk clusters.[/]"
    console.print(Panel(t, title="Residency Check", border_style="cyan"))


def _fmt_size(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:,.0f} {u}"
        b /= 1024
    return f"{b:,.1f} TB"
