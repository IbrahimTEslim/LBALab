"""
Lesson 4: File Residency
=========================

NTFS has a clever optimization: if a file is small enough, its data is
stored **inside the MFT record itself** — no separate clusters needed.

This is called **resident** storage:

    ┌─ MFT Record (1024 bytes) ──────────────────┐
    │ Header (48 bytes)                           │
    │ $STANDARD_INFORMATION attribute (~72 bytes) │
    │ $FILE_NAME attribute (~100 bytes)           │
    │ $DATA attribute:                            │
    │   ┌─────────────────────────────────────┐   │
    │   │ [THE ACTUAL FILE CONTENT IS HERE]   │   │
    │   │ (fits because file is small)        │   │
    │   └─────────────────────────────────────┘   │
    │ End marker (0xFFFFFFFF)                     │
    │ Unused space                                │
    └─────────────────────────────────────────────┘

When a file is too large (typically > ~700 bytes), NTFS moves the data
to separate clusters.  The $DATA attribute then stores a **run list**
(VCN → LCN mapping) instead of the actual content.  This is called
**non-resident** storage:

    ┌─ MFT Record ───────────────────────────────┐
    │ Header                                      │
    │ $STANDARD_INFORMATION                       │
    │ $FILE_NAME                                  │
    │ $DATA attribute:                            │
    │   ┌─────────────────────────────────────┐   │
    │   │ Run list: VCN 0-48 → LCN 1234567   │   │
    │   │ (pointer to clusters, not content)  │   │
    │   └─────────────────────────────────────┘   │
    │ End marker                                  │
    └─────────────────────────────────────────────┘

    Clusters on disk:
    ┌──────────────────────────────────────────┐
    │ LCN 1234567: [ACTUAL FILE CONTENT HERE]  │
    │ LCN 1234568: [MORE CONTENT...]           │
    └──────────────────────────────────────────┘

Why this matters for forensics:
- Resident files can ONLY be recovered by parsing the MFT
- Non-resident files can be recovered from their disk clusters
- Deleted resident files may be overwritten when the MFT record is reused
"""
import os
from rich.panel import Panel
from rich.table import Table
from ntfs_toolkit.explorer.animate import (
    console, typewriter, panel_build, scan_line, flash_result,
)
from ntfs_toolkit.analyzers import ResidencyChecker, FileAnalyzer


def run(drive_letter="C", animate=False):
    console.print()
    typewriter("  Lesson 4: File Residency", style="bold magenta",
               enabled=animate)
    console.rule("[bold magenta]Lesson 4: File Residency[/]")

    # --- Concept ---
    concept = [
        "",
        "  NTFS stores small files [bold]inside[/] the MFT record itself.",
        "  This is called [bold green]RESIDENT[/] storage.",
        "",
        "  Larger files are stored in separate disk clusters.",
        "  The MFT record only holds a pointer (run list).",
        "  This is called [bold yellow]NON-RESIDENT[/] storage.",
        "",
        "  The threshold is roughly [bold]~700 bytes[/] — it depends on",
        "  how much space other attributes use in the MFT record.",
        "",
        "  [dim]Resident:[/]   data IN the MFT record  → fast, no extra I/O",
        "  [dim]Non-resident:[/] data in clusters on disk → needs extent lookup",
        "",
    ]
    panel_build(concept, title="Resident vs Non-Resident",
                style="magenta", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(concept),
                            title="Resident vs Non-Resident",
                            border_style="magenta"))

    # --- Live demo: check files on the drive ---
    console.print(f"\n  [bold]Scanning files on {drive_letter}: "
                  f"to find resident and non-resident examples...[/]\n")

    checker = ResidencyChecker()
    fa = FileAnalyzer()

    # Find some test files
    test_paths = _find_test_files(drive_letter)
    if not test_paths:
        console.print("  [red]No test files found on this drive.[/]")
        return

    t = Table(title=f"Residency Check — Volume {drive_letter}:")
    t.add_column("File", style="bold")
    t.add_column("Size", justify="right")
    t.add_column("Status")
    t.add_column("MFT Record", justify="right")

    for path in test_paths:
        try:
            size = os.path.getsize(path)
            is_res = checker.is_file_resident(path)
            info = fa.get_file_info(path)
            name = os.path.basename(path)
            if len(name) > 30:
                name = name[:27] + "..."
            status = "[green]RESIDENT[/]" if is_res \
                else "[yellow]NON-RESIDENT[/]"
            t.add_row(name, f"{size:,}", status,
                      f"{info['mft_record_number']:,}")
        except Exception:
            continue

    console.print(t)

    # --- Why it matters ---
    forensics = [
        "",
        "  [bold yellow]Why Residency Matters for Forensics:[/]",
        "",
        "  [bold green]Resident files:[/]",
        "  • Data is embedded in the MFT record",
        "  • Recovery requires MFT parsing (not cluster scanning)",
        "  • When the MFT record is reused, data is gone forever",
        "  • Standard file recovery tools may miss these",
        "",
        "  [bold yellow]Non-resident files:[/]",
        "  • Data lives in clusters that can be scanned independently",
        "  • Even after deletion, clusters may not be overwritten yet",
        "  • File carving tools can find content by signature scanning",
        "  • Fragmented files have multiple cluster runs to track",
        "",
    ]
    panel_build(forensics, title="Forensic Implications", style="yellow",
                enabled=animate)
    if not animate:
        console.print(Panel("\n".join(forensics),
                            title="Forensic Implications",
                            border_style="yellow"))

    # --- Takeaway ---
    takeaway = [
        "",
        "  [bold green]Key Takeaways:[/]",
        "  • Files < ~700 bytes are usually resident (data in MFT)",
        "  • Files > ~700 bytes are non-resident (data in clusters)",
        "  • Residency is detected by checking for cluster allocations",
        "  • Resident data needs MFT parsing; non-resident needs LBA reading",
        "  • This distinction is critical for forensic recovery strategy",
        "",
    ]
    panel_build(takeaway, title="Summary", style="green", enabled=animate)
    if not animate:
        console.print(Panel("\n".join(takeaway), title="Summary",
                            border_style="green"))


def _find_test_files(drive_letter):
    """Find a mix of small and large files for demonstration."""
    candidates = []
    # Common small files (likely resident)
    for name in ("desktop.ini", "thumbs.db"):
        for root_dir in (f"{drive_letter}:\\",
                         f"{drive_letter}:\\Windows"):
            path = os.path.join(root_dir, name)
            if os.path.isfile(path):
                candidates.append(path)
    # Try to find files in root of drive
    try:
        for entry in os.scandir(f"{drive_letter}:\\"):
            if entry.is_file() and len(candidates) < 8:
                candidates.append(entry.path)
    except Exception:
        pass
    return candidates[:8]
