"""
Lesson 6: What Happens When You Delete a File?
================================================

When you delete a file in Windows (even from Recycle Bin), NTFS does
surprisingly little to the actual data:

Step 1: The MFT record's IN_USE flag is cleared (bit 0 of flags)
    Before: flags = 0x0001 (IN_USE)
    After:  flags = 0x0000 (FREE)

Step 2: The directory index entry ($I30) is removed
    The parent folder no longer lists the file.

Step 3: The clusters are marked as free in $Bitmap
    The cluster allocation bitmap is updated so those clusters
    can be reused by new files.

What does NOT happen:
    ✗ The file content is NOT zeroed or overwritten
    ✗ The MFT record is NOT erased (just marked free)
    ✗ The run list (VCN→LCN mapping) is NOT removed
    ✗ The file name is NOT removed from the MFT record

This is why file recovery works — the data is still on disk until
something else overwrites those clusters.

    ┌─ Before Deletion ──────────────────────────┐
    │ MFT Record: flags=IN_USE, $DATA→LCN 5000  │
    │ $Bitmap: clusters 5000-5010 = ALLOCATED    │
    │ Directory: "secret.docx" → MFT #1234       │
    │ Disk clusters 5000-5010: [FILE CONTENT]    │
    └────────────────────────────────────────────┘

    ┌─ After Deletion ───────────────────────────┐
    │ MFT Record: flags=FREE, $DATA→LCN 5000    │  ← still there!
    │ $Bitmap: clusters 5000-5010 = FREE         │  ← marked free
    │ Directory: (entry removed)                 │
    │ Disk clusters 5000-5010: [FILE CONTENT]    │  ← still there!
    └────────────────────────────────────────────┘

Recovery tools work by:
1. Scanning MFT for records with flags=FREE but valid $DATA
2. Reading the run list to find where data was stored
3. Reading those clusters directly — content is usually intact
"""
import os
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, scan_line, decode_reveal,
)
from ntfs_toolkit.analyzers import ComprehensiveAnalyzer, LBAReader


def run(drive_letter="C", animate=False):
    console.print()
    typewriter("  Lesson 6: What Happens When You Delete a File?",
               style="bold magenta", enabled=animate)
    console.rule("[bold magenta]Lesson 6: Deleted Files[/]")

    # --- What deletion actually does ---
    deletion = [
        "",
        "  When you delete a file, NTFS does [bold]three things[/]:",
        "",
        "  [bold red]1.[/] MFT record: IN_USE flag cleared (0x0001 → 0x0000)",
        "     The record is marked as free for reuse.",
        "",
        "  [bold red]2.[/] Directory index: entry removed from parent folder",
        "     The file name disappears from dir listings.",
        "",
        "  [bold red]3.[/] $Bitmap: clusters marked as free",
        "     Those clusters can now be allocated to new files.",
        "",
        "  [bold green]What does NOT happen:[/]",
        "  • File content is [bold]NOT[/] zeroed or overwritten",
        "  • MFT record is [bold]NOT[/] erased (just flag change)",
        "  • Run list (VCN→LCN) is [bold]NOT[/] removed",
        "  • File name is [bold]NOT[/] removed from MFT record",
        "",
    ]
    panel_build(deletion, title="What Deletion Does", style="red",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(deletion),
                            title="What Deletion Does",
                            border_style="red"))

    # --- Visual: before vs after ---
    before_after = [
        "",
        "  [bold cyan]Before deletion:[/]",
        "  MFT flags = [green]IN_USE[/]  |  $Bitmap = [green]ALLOCATED[/]"
        "  |  Dir = [green]listed[/]",
        "  Disk clusters: [green][FILE CONTENT INTACT][/]",
        "",
        "  [bold red]After deletion:[/]",
        "  MFT flags = [red]FREE[/]     |  $Bitmap = [red]FREE[/]"
        "       |  Dir = [red]removed[/]",
        "  Disk clusters: [yellow][FILE CONTENT STILL INTACT!][/]",
        "",
        "  The data survives until those clusters are reused.",
        "",
    ]
    panel_build(before_after, title="Before vs After", style="yellow",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(before_after),
                            title="Before vs After",
                            border_style="yellow"))

    # --- Live demo: show MFT record #0 flags ---
    console.print(f"\n  [bold]Let's look at a live MFT record to see"
                  f" the IN_USE flag...[/]\n")

    ca = ComprehensiveAnalyzer()
    # Record 5 = root directory (always IN_USE)
    result = ca.analyze_mft_record(drive_letter, 5)
    hdr = result.get("header")
    if hdr:
        flag_demo = (
            f"  MFT Record #5 (root directory):\n"
            f"  Flags raw value: 0x{hdr['flags']:04x}\n"
            f"  Flags meaning:   {hdr['flags_description']}\n"
            f"  IN_USE bit:      {'SET (file exists)' if hdr['is_in_use'] else 'CLEAR (deleted)'}\n"
            f"  DIRECTORY bit:   {'SET' if hdr['is_directory'] else 'CLEAR'}\n\n"
            f"  When a file is deleted, only the IN_USE bit changes:\n"
            f"  0x0001 (IN_USE) → 0x0000 (FREE)\n"
            f"  That's it. One bit flip. Everything else stays."
        )
        decode_reveal(flag_demo, title="Live: MFT Flags", style="cyan",
                      enabled=animate)
        if not animate:
            console.print(Panel(flag_demo, title="Live: MFT Flags",
                                border_style="cyan"))

    # --- How recovery works ---
    recovery = [
        "",
        "  [bold cyan]How File Recovery Works:[/]",
        "",
        "  [dim]Step 1:[/] Scan MFT for records where flags = FREE",
        "          but the record still has valid attributes.",
        "",
        "  [dim]Step 2:[/] Parse the $DATA attribute's run list",
        "          to find which clusters held the file data.",
        "",
        "  [dim]Step 3:[/] Read those clusters directly from disk.",
        "          If nothing has overwritten them, the data is intact.",
        "",
        "  [dim]Step 4:[/] Reconstruct the file from the cluster data.",
        "",
        "  [bold yellow]The window of recovery:[/]",
        "  • Immediately after deletion: [green]very likely recoverable[/]",
        "  • After some disk activity: [yellow]partially recoverable[/]",
        "  • After heavy disk use: [red]clusters may be overwritten[/]",
        "  • After secure wipe: [red]impossible to recover[/]",
        "",
    ]
    panel_build(recovery, title="How Recovery Works", style="cyan",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(recovery),
                            title="How Recovery Works",
                            border_style="cyan"))

    # --- Why secure deletion is hard ---
    secure = [
        "",
        "  [bold red]Why Secure Deletion is Difficult:[/]",
        "",
        "  Simply overwriting the file content is not enough because:",
        "",
        "  • The [bold]MFT record[/] still has the file name and metadata",
        "  • The [bold]$LogFile[/] (journal) recorded the file operations",
        "  • The [bold]$UsnJrnl[/] (change journal) logged the creation",
        "  • [bold]$MFTMirr[/] has a backup of the first MFT records",
        "  • On SSDs, [bold]wear leveling[/] may keep old copies in spare cells",
        "  • [bold]Volume Shadow Copies[/] may have snapshots",
        "",
        "  True secure deletion must address ALL of these locations.",
        "  This is what the 'dangerous' module in this toolkit does.",
        "",
    ]
    panel_build(secure, title="Why Secure Deletion is Hard",
                style="red", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(secure),
                            title="Why Secure Deletion is Hard",
                            border_style="red"))

    # --- Takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • Deletion only flips the IN_USE flag and frees clusters",
        "  • File content remains on disk until overwritten by new data",
        "  • Recovery works by reading the still-intact MFT run list",
        "  • The recovery window shrinks as the disk is used",
        "  • Secure deletion must wipe content, MFT, journals, and mirrors",
        "  • SSDs add complexity with wear leveling and TRIM",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))
