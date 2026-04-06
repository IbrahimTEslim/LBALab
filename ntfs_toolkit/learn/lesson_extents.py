"""
Lesson 5: Extent Mapping (VCN → LCN → LBA)
============================================

When a file is non-resident, NTFS stores its data in **clusters** on disk.
The mapping from file-logical to disk-physical is done through **extents**:

    File's view (Virtual):     Disk's view (Physical):

    VCN 0  ─────────────────→  LCN 50,000  (cluster on disk)
    VCN 1  ─────────────────→  LCN 50,001
    VCN 2  ─────────────────→  LCN 50,002
    ...contiguous...           ...contiguous...
    VCN 48 ─────────────────→  LCN 50,048

This contiguous run is one **extent**.  A fragmented file has multiple:

    Extent 1: VCN 0-48   → LCN 50,000  (first fragment)
    Extent 2: VCN 49-100 → LCN 80,000  (second fragment, different location)

The three address levels:

    VCN (Virtual Cluster Number)
    │   The cluster's position within the file (0, 1, 2, ...)
    │   VCN 0 = first cluster of file data
    ▼
    LCN (Logical Cluster Number)
    │   The cluster's position on the NTFS volume
    │   LCN 0 = first cluster of the volume
    ▼
    LBA (Logical Block Address)
    │   The sector's position on the physical disk
    │   LBA = partition_start + (LCN × sectors_per_cluster)
    ▼
    Physical byte offset = LBA × 512
"""
import os
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, decode_reveal, flash_result,
)
from ntfs_toolkit.analyzers import ExtentMapper, FileAnalyzer


def run(drive_letter="C", animate=False, file_path=None):
    console.print()
    typewriter("  Lesson 5: Extent Mapping (VCN -> LCN -> LBA)",
               style="bold magenta", enabled=animate)
    console.rule("[bold magenta]Lesson 5: Extent Mapping[/]")

    # --- The three address levels ---
    levels = [
        "",
        "  NTFS uses three levels of addressing:",
        "",
        "  [bold cyan]VCN[/] (Virtual Cluster Number)",
        "    Cluster position [bold]within the file[/] (0, 1, 2, ...)",
        "    VCN 0 = first cluster of the file's data",
        "",
        "  [bold yellow]LCN[/] (Logical Cluster Number)",
        "    Cluster position [bold]on the volume[/]",
        "    The MFT stores VCN-to-LCN mappings (run list)",
        "",
        "  [bold green]LBA[/] (Logical Block Address)",
        "    Sector position [bold]on the physical disk[/]",
        "    LBA = partition_start + (LCN x sectors_per_cluster)",
        "",
        "  [bold]Byte offset[/] = LBA x 512",
        "",
    ]
    panel_build(levels, title="VCN → LCN → LBA", style="magenta",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(levels), title="VCN → LCN → LBA",
                            border_style="magenta"))

    # --- Live demo ---
    target = file_path or _find_nonresident_file(drive_letter)
    if not target:
        console.print("  [red]No non-resident file found for demo.[/]")
        return

    console.print(f"\n  [bold]Mapping extents for: {target}[/]\n")

    mapper = ExtentMapper()
    fa = FileAnalyzer()
    result = mapper.map_extents_to_lba(target)

    if result["is_resident"]:
        console.print("  [green]This file is resident — no extents.[/]")
        return

    part_lba = result["partition_lba"]
    spc = result["sectors_per_cluster"]

    # Show the conversion formula
    formula = (
        f"  File: {os.path.basename(target)}\n"
        f"  Size: {os.path.getsize(target):,} bytes\n"
        f"  Partition start LBA: {part_lba:,}\n"
        f"  Sectors per cluster: {spc}\n\n"
        f"  Formula:\n"
        f"  [bold]LBA = {part_lba:,} + (LCN x {spc})[/]"
    )
    decode_reveal(formula, title="Conversion Formula", style="cyan",
                  enabled=animate)
    if not animate:
        console.print(Panel(formula, title="Conversion Formula",
                            border_style="cyan"))

    # Show extent table
    t = Table(title="File Extent Map")
    t.add_column("#", style="dim", justify="right")
    t.add_column("VCN Range")
    t.add_column("Clusters", justify="right")
    t.add_column("LCN", justify="right")
    t.add_column("LBA (abs)", justify="right", style="bold")
    t.add_column("Byte Offset", justify="right")
    t.add_column("Size", justify="right")

    for i, ext in enumerate(result["extents"], 1):
        vcn = f"{ext['start_vcn']}-{ext['next_vcn'] - 1}"
        cl = f"{ext['cluster_count']:,}"
        if ext["type"] == "sparse":
            t.add_row(str(i), vcn, cl, "-", "-", "-", "[red]SPARSE[/]")
        else:
            t.add_row(str(i), vcn, cl, f"{ext['lcn']:,}",
                      f"{ext['lba_absolute']:,}",
                      f"{ext['byte_offset']:,}",
                      f"{ext['size_bytes']:,}")
    console.print(t)

    # Show step-by-step for first extent
    if result["extents"] and result["extents"][0]["type"] == "allocated":
        ext = result["extents"][0]
        _show_calculation(ext, part_lba, spc, animate)

    # --- Fragmentation ---
    n_extents = len(result["extents"])
    frag_info = [
        "",
        f"  This file has [bold]{n_extents}[/] extent(s).",
    ]
    if n_extents == 1:
        frag_info.append("  [green]Not fragmented[/] — all data is contiguous.")
    else:
        frag_info.append(f"  [yellow]Fragmented[/] — data is split across"
                         f" {n_extents} non-contiguous regions.")
        frag_info.append("  The disk head must seek between regions (slower on HDD).")
    frag_info.append("")
    panel_build(frag_info, title="Fragmentation", style="yellow",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(frag_info), title="Fragmentation",
                            border_style="yellow"))

    # --- Takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • VCN = file-relative cluster, LCN = volume cluster, LBA = disk sector",
        "  • LBA = partition_start + (LCN x sectors_per_cluster)",
        "  • Each contiguous run of clusters is one extent",
        "  • Multiple extents = fragmented file",
        "  • This mapping is how forensic tools locate file data on disk",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))


def _show_calculation(ext, part_lba, spc, animate):
    """Step-by-step LBA calculation for one extent."""
    steps = [
        "",
        f"  [dim]Step 1:[/] LCN = {ext['lcn']:,}",
        f"  [dim]Step 2:[/] Relative LBA = {ext['lcn']:,} x {spc}"
        f" = {ext['lba_relative']:,}",
        f"  [dim]Step 3:[/] Absolute LBA = {part_lba:,} +"
        f" {ext['lba_relative']:,} = [bold]{ext['lba_absolute']:,}[/]",
        f"  [dim]Step 4:[/] Byte offset = {ext['lba_absolute']:,} x 512"
        f" = [bold]{ext['byte_offset']:,}[/]",
        "",
    ]
    panel_build(steps, title="Calculation (Extent 1)", style="cyan",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(steps),
                            title="Calculation (Extent 1)",
                            border_style="cyan"))


def _find_nonresident_file(drive_letter):
    """Find a non-resident file on the drive for demonstration."""
    mapper = ExtentMapper()
    try:
        for entry in os.scandir(f"{drive_letter}:\\"):
            if entry.is_file() and entry.stat().st_size > 1024:
                try:
                    exts = mapper.get_file_extents(entry.path)
                    if exts is not None:
                        return entry.path
                except Exception:
                    continue
    except Exception:
        pass
    return None
