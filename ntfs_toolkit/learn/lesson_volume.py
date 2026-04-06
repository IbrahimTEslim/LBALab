"""
Lesson 2: NTFS Volume Structure
================================

An NTFS volume has a specific layout on disk.  Understanding this layout
is essential for forensics — it tells you where everything lives.

The layout from LBA 0 onwards:

    ┌──────────────┐  LBA 0
    │ Boot Sector  │  Contains volume geometry, MFT location
    ├──────────────┤  LBA 1
    │ Boot Code    │  NTFS bootstrap code (continues from boot sector)
    ├──────────────┤
    │   ...        │  Reserved sectors
    ├──────────────┤  LBA = MFT start cluster × sectors_per_cluster
    │              │
    │   $MFT       │  Master File Table — index of every file
    │              │
    ├──────────────┤
    │              │
    │  Data Area   │  Where actual file content is stored in clusters
    │              │
    ├──────────────┤
    │  $MFTMirr    │  Backup of first 4 MFT records (usually mid-volume)
    ├──────────────┤
    │ Boot Backup  │  Copy of boot sector (last sector of volume)
    └──────────────┘

Key concepts:
- **Cluster**: The allocation unit. Files are stored in clusters, not sectors.
  A cluster is typically 4,096 bytes (8 sectors).
- **LCN**: Logical Cluster Number — the cluster's position on the volume.
- **Partition offset**: The volume doesn't start at LBA 0 of the physical
  disk. There's a partition table first (usually at LBA 2048).
"""
from rich.panel import Panel
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, decode_reveal,
)
from ntfs_toolkit.analyzers import FileAnalyzer


def run(drive_letter="C", animate=False):
    console.print()
    typewriter("  Lesson 2: NTFS Volume Structure", style="bold magenta",
               enabled=animate)
    console.rule("[bold magenta]Lesson 2: NTFS Volume Structure[/]")

    # --- Volume layout diagram ---
    layout = [
        "",
        "  An NTFS volume is organized like this:",
        "",
        "  [dim]LBA 0[/]          [bold]Boot Sector[/]     (volume geometry, MFT pointer)",
        "  [dim]LBA 1..N[/]       [bold]Reserved[/]        (boot code, padding)",
        "  [dim]LBA M[/]          [bold]$MFT[/]            (Master File Table starts here)",
        "  [dim]LBA M+...[/]      [bold]Data Area[/]       (file content in clusters)",
        "  [dim]mid-volume[/]     [bold]$MFTMirr[/]        (backup of first 4 MFT records)",
        "  [dim]last LBA[/]       [bold]Boot Backup[/]     (copy of boot sector)",
        "",
        "  The [bold]cluster[/] is the allocation unit — files occupy whole clusters.",
        "  A cluster is typically [bold]4,096 bytes[/] = 8 sectors of 512 bytes.",
        "",
    ]
    panel_build(layout, title="Volume Layout", style="magenta",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(layout), title="Volume Layout",
                            border_style="magenta"))

    # --- Read live volume geometry ---
    fa = FileAnalyzer()
    console.print(f"\n  [bold]Reading volume geometry for {drive_letter}:...[/]\n")

    vol = fa.get_volume_info(drive_letter)
    part_lba = fa.get_partition_start_lba(drive_letter)
    spc, bps = fa.get_sectors_per_cluster(drive_letter)

    cluster_size = vol["bytes_per_cluster"]
    mft_lba = vol["mft_start_lcn"] * spc
    total_size = vol["total_clusters"] * cluster_size
    free_size = vol["free_clusters"] * cluster_size
    used_pct = ((vol["total_clusters"] - vol["free_clusters"])
                / max(vol["total_clusters"], 1)) * 100

    geo = (
        f"  Partition starts at LBA  {part_lba:,}\n"
        f"  Bytes per sector         {bps}\n"
        f"  Bytes per cluster        {cluster_size:,}\n"
        f"  Sectors per cluster      {spc}\n"
        f"  Total clusters           {vol['total_clusters']:,}\n"
        f"  Free clusters            {vol['free_clusters']:,}\n"
        f"  Volume size              {total_size:,} bytes "
        f"({total_size / (1024**3):.1f} GB)\n"
        f"  Free space               {free_size:,} bytes "
        f"({free_size / (1024**3):.1f} GB)\n"
        f"  Used                     {used_pct:.1f}%\n"
        f"  MFT starts at LCN       {vol['mft_start_lcn']:,}\n"
        f"  MFT starts at LBA       {mft_lba:,}  (relative to volume)\n"
        f"  MFT record size          {vol['mft_record_size']} bytes"
    )
    decode_reveal(geo, title=f"Volume {drive_letter}: Geometry (Live)",
                  style="cyan", enabled=animate)
    if not animate:
        console.print(Panel(geo, title=f"Volume {drive_letter}: Geometry (Live)",
                            border_style="cyan"))

    # --- Explain partition offset ---
    offset_info = [
        "",
        "  [bold yellow]Important: Partition Offset[/]",
        "",
        f"  Your volume {drive_letter}: starts at LBA [bold]{part_lba:,}[/]"
        f" on the physical disk.",
        f"  That means LBA 0 of the volume = LBA {part_lba:,} on the disk.",
        "",
        "  When converting volume-relative addresses to physical disk addresses:",
        f"  [bold]physical_LBA = {part_lba:,} + volume_relative_LBA[/]",
        "",
        f"  Example: MFT at volume LBA {mft_lba:,} = physical LBA"
        f" [bold]{part_lba + mft_lba:,}[/]",
        "",
    ]
    panel_build(offset_info, title="Partition Offset", style="yellow",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(offset_info), title="Partition Offset",
                            border_style="yellow"))

    # --- Takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • Clusters are the allocation unit (typically 4 KB = 8 sectors)",
        "  • The MFT is the index of every file — its location is in the boot sector",
        "  • Volume LBAs are offset from the physical disk by the partition start",
        "  • physical_LBA = partition_start + volume_relative_LBA",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))
