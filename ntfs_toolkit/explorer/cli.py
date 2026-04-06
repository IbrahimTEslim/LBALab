"""
CLI — Interactive NTFS explorer with rich terminal UI.

Run directly::

    python -m ntfs_toolkit.explorer

Or with arguments::

    python -m ntfs_toolkit.explorer --analyze-file "C:\\Windows\\notepad.exe"
    python -m ntfs_toolkit.explorer --read-lba F:0 --animate
"""
import os
import sys
import argparse

from rich.panel import Panel
from rich.prompt import Prompt

from ntfs_toolkit.core import WindowsAPI
from ntfs_toolkit.analyzers import (
    ComprehensiveAnalyzer, LBAReader, ResidencyChecker,
)
from ntfs_toolkit.explorer.display import (
    show_file_analysis, show_mft_record, show_hex_panel, show_residency,
)
from ntfs_toolkit.explorer.animate import console


def interactive_mode(animate=False):
    """Main interactive menu loop."""
    ca = ComprehensiveAnalyzer()
    reader = LBAReader()
    checker = ResidencyChecker()

    MENU = (
        "\n"
        "[bold cyan]1[/] │ Analyze file         — full NTFS layout\n"
        "[bold cyan]2[/] │ Read LBA             — hex dump of any sector\n"
        "[bold cyan]3[/] │ Check residency      — resident vs non-resident\n"
        "[bold cyan]4[/] │ Analyze MFT record   — parse by record number\n"
        "[bold cyan]q[/] │ Quit"
    )

    console.print(Panel(
        "[bold]NTFS Toolkit Explorer[/]\n[dim]Interactive NTFS forensics and analysis[/]",
        border_style="cyan",
    ))

    if not WindowsAPI.is_admin():
        console.print("[yellow]⚠ Not running as Administrator — some operations may fail.[/]\n")

    while True:
        console.print(Panel(MENU, title="Options", border_style="blue"))
        choice = Prompt.ask("[bold]Choose", choices=["1", "2", "3", "4", "q"], default="q")

        if choice == "1":
            _do_analyze_file(ca, animate)
        elif choice == "2":
            _do_read_lba(reader, animate)
        elif choice == "3":
            _do_check_residency(checker)
        elif choice == "4":
            _do_analyze_mft(ca, animate)
        elif choice == "q":
            break


def _do_analyze_file(ca, animate):
    path = Prompt.ask("  File path").strip().strip('"')
    if not path or not os.path.exists(path):
        console.print("[red]  Path not found.[/]")
        return
    try:
        result = ca.analyze(path)
        show_file_analysis(result, animate=animate)
    except Exception as e:
        console.print(f"[red]  Error: {e}[/]")


def _do_read_lba(reader, animate):
    drive = Prompt.ask("  Drive (0=PhysicalDrive0, C=Volume C:)").strip()
    try:
        lba = int(Prompt.ask("  LBA"))
    except ValueError:
        console.print("[red]  Invalid LBA.[/]")
        return
    try:
        if drive.isdigit():
            data = reader.read_physical(int(drive), lba, 512)
            title = f"PhysicalDrive{drive} — LBA {lba}"
        else:
            data = reader.read_volume(drive, lba, 512)
            title = f"Volume {drive}: — LBA {lba}"
        show_hex_panel(data, title=title, animate=animate)
        if data[:4] == b"FILE":
            console.print("  [bold yellow]⚡ MFT record signature detected[/]")
        if b"NTFS" in data[:16]:
            console.print("  [bold yellow]⚡ NTFS boot sector detected[/]")
    except Exception as e:
        console.print(f"[red]  Error: {e}[/]")


def _do_check_residency(checker):
    path = Prompt.ask("  File path").strip().strip('"')
    if not path or not os.path.exists(path):
        console.print("[red]  Path not found.[/]")
        return
    try:
        is_res = checker.is_file_resident(path)
        show_residency(path, is_res, os.path.getsize(path))
    except Exception as e:
        console.print(f"[red]  Error: {e}[/]")


def _do_analyze_mft(ca, animate):
    drive = Prompt.ask("  Drive letter", default="C").strip().upper()
    try:
        rec = int(Prompt.ask("  MFT record number"))
    except ValueError:
        console.print("[red]  Invalid record number.[/]")
        return
    try:
        result = ca.analyze_mft_record(drive, rec)
        show_mft_record(result, animate=animate)
    except Exception as e:
        console.print(f"[red]  Error: {e}[/]")


def main():
    parser = argparse.ArgumentParser(description="NTFS Toolkit Explorer")
    parser.add_argument("--analyze-file", metavar="PATH", help="Analyze file")
    parser.add_argument("--read-lba", metavar="DRIVE:LBA", help="Read LBA (e.g. F:0)")
    parser.add_argument("--check-residency", metavar="PATH", help="Check residency")
    parser.add_argument("--mft-record", metavar="DRIVE:NUM", help="MFT record (e.g. C:5)")
    parser.add_argument("--animate", action="store_true", help="Enable animations")
    args = parser.parse_args()

    ca = ComprehensiveAnalyzer()
    reader = LBAReader()
    checker = ResidencyChecker()

    if args.analyze_file:
        show_file_analysis(ca.analyze(args.analyze_file), animate=args.animate)
    elif args.read_lba:
        drive, lba = args.read_lba.split(":")
        lba = int(lba)
        if drive.isdigit():
            data = reader.read_physical(int(drive), lba, 512)
        else:
            data = reader.read_volume(drive, lba, 512)
        show_hex_panel(data, title=f"{drive}:{lba}", animate=args.animate)
    elif args.check_residency:
        res = checker.is_file_resident(args.check_residency)
        show_residency(args.check_residency, res, os.path.getsize(args.check_residency))
    elif args.mft_record:
        d, n = args.mft_record.split(":")
        show_mft_record(ca.analyze_mft_record(d.upper(), int(n)), animate=args.animate)
    else:
        interactive_mode(animate=args.animate)


if __name__ == "__main__":
    main()
