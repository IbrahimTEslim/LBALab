"""
Lesson 1: What is an LBA?
==========================

Every storage device — HDD, SSD, USB drive — is divided into fixed-size
blocks called **sectors**.  A sector is the smallest unit the drive can
read or write, typically **512 bytes**.

An **LBA (Logical Block Address)** is simply the sector number, counting
from zero:

    LBA 0  = first sector on the disk  (usually the boot sector)
    LBA 1  = second sector
    LBA 2  = third sector
    ...

To find the byte offset of any LBA::

    byte_offset = LBA × sector_size
    byte_offset = LBA × 512

For example, LBA 2048 starts at byte 1,048,576 (exactly 1 MB into the disk).
This is where most modern partitions begin.

In this lesson we will:
1. Read LBA 0 of your volume — the NTFS boot sector.
2. Parse the boot sector to extract key NTFS parameters.
3. Understand what each field means.
"""
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, hex_reveal, EFFECT_DURATION,
)
from ntfs_toolkit.analyzers import LBAReader


def run(drive_letter="C", animate=False):
    console.print()
    typewriter("  Lesson 1: What is an LBA?", style="bold magenta",
               enabled=animate)
    console.rule("[bold magenta]Lesson 1: What is an LBA?[/]")

    # --- Concept explanation ---
    explanation = [
        "",
        "  Your disk is divided into [bold]sectors[/] — fixed 512-byte blocks.",
        "  Each sector has a number called an [bold]LBA[/] (Logical Block Address).",
        "",
        "  [dim]LBA 0[/]  = first sector   (byte offset 0)",
        "  [dim]LBA 1[/]  = second sector  (byte offset 512)",
        "  [dim]LBA 2[/]  = third sector   (byte offset 1,024)",
        "  [dim]...[/]",
        f"  [dim]LBA N[/]  = byte offset = N x 512",
        "",
        "  Let's read [bold]LBA 0[/] of your volume — the NTFS boot sector.",
        "",
    ]
    panel_build(explanation, title="Concept: Sectors & LBAs",
                style="magenta", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(explanation),
                            title="Concept: Sectors & LBAs",
                            border_style="magenta"))

    # --- Read boot sector ---
    reader = LBAReader()
    console.print(f"\n  [bold]Reading LBA 0 from volume {drive_letter}:...[/]\n")
    boot = reader.read_volume(drive_letter, 0, 512)
    hex_reveal(boot[:64], title=f"Volume {drive_letter}: — LBA 0 (Boot Sector)",
               enabled=animate)
    if not animate:
        from ntfs_toolkit.explorer.display import show_hex_panel
        show_hex_panel(boot[:64], title=f"Volume {drive_letter}: — LBA 0")

    # --- Parse boot sector fields ---
    console.print()
    _parse_boot_sector(boot, drive_letter, animate)

    # --- Key takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • Every byte on disk has an address: LBA x 512",
        "  • LBA 0 holds the NTFS boot sector with volume geometry",
        "  • The boot sector tells the OS where to find the MFT",
        "  • All NTFS analysis starts from these boot sector values",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))


def _parse_boot_sector(boot, drive_letter, animate):
    """Parse and display NTFS boot sector fields."""
    if len(boot) < 84:
        console.print("[red]  Boot sector too small to parse.[/]")
        return

    # Extract fields from known offsets
    oem_id = boot[3:11].decode("ascii", errors="replace").strip()
    bytes_per_sector = int.from_bytes(boot[11:13], "little")
    sectors_per_cluster = boot[13]
    total_sectors = int.from_bytes(boot[40:48], "little")
    mft_cluster = int.from_bytes(boot[48:56], "little")
    mft_mirror_cluster = int.from_bytes(boot[56:64], "little")
    mft_record_clusters = boot[64]
    # Negative value means 2^|value| bytes
    if mft_record_clusters > 127:
        mft_record_size = 2 ** (256 - mft_record_clusters)
    else:
        mft_record_size = mft_record_clusters * sectors_per_cluster * bytes_per_sector

    cluster_size = sectors_per_cluster * bytes_per_sector
    total_bytes = total_sectors * bytes_per_sector
    mft_lba = mft_cluster * sectors_per_cluster

    fields = [
        "",
        "  Here's what the boot sector tells us about this volume:",
        "",
        f"  [dim]Bytes 3-10:[/]   OEM ID             = [bold]{oem_id}[/]",
        f"  [dim]Bytes 11-12:[/]  Bytes per sector   = [bold]{bytes_per_sector}[/]",
        f"  [dim]Byte 13:[/]      Sectors per cluster = [bold]{sectors_per_cluster}[/]",
        f"                   Cluster size       = [bold]{cluster_size:,} bytes[/]",
        f"  [dim]Bytes 40-47:[/]  Total sectors      = [bold]{total_sectors:,}[/]",
        f"                   Volume size        = [bold]{total_bytes:,} bytes"
        f" ({total_bytes / (1024**3):.1f} GB)[/]",
        f"  [dim]Bytes 48-55:[/]  MFT start cluster  = [bold]{mft_cluster:,}[/]",
        f"                   MFT start LBA     = [bold]{mft_lba:,}[/]",
        f"  [dim]Bytes 56-63:[/]  MFT mirror cluster = [bold]{mft_mirror_cluster:,}[/]",
        f"  [dim]Byte 64:[/]      MFT record size    = [bold]{mft_record_size:,} bytes[/]",
        "",
        f"  [yellow]The MFT (Master File Table) starts at LBA {mft_lba:,}[/]",
        f"  [yellow]That's byte offset {mft_lba * bytes_per_sector:,} on the volume.[/]",
        "",
    ]
    panel_build(fields, title="Boot Sector Decoded", style="cyan",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(fields), title="Boot Sector Decoded",
                            border_style="cyan"))
