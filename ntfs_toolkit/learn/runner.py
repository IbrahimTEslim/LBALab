"""Lesson runner — menu and CLI for the NTFS Learning Lab."""
import argparse
from rich.panel import Panel
from rich.prompt import Prompt
from ntfs_toolkit.explorer.animate import console, typewriter
from ntfs_toolkit.learn import (
    lesson_lba, lesson_volume, lesson_mft,
    lesson_residency, lesson_extents, lesson_deletion,
)

LESSONS = [
    ("1", "What is an LBA?", lesson_lba),
    ("2", "NTFS Volume Structure", lesson_volume),
    ("3", "MFT Records", lesson_mft),
    ("4", "File Residency", lesson_residency),
    ("5", "Extent Mapping (VCN → LCN → LBA)", lesson_extents),
    ("6", "Deleted Files & Recovery", lesson_deletion),
]


def interactive(drive, animate):
    """Interactive lesson menu."""
    console.print()
    typewriter("  NTFS Internals — Learning Lab", style="bold magenta",
               enabled=animate)
    console.print()

    while True:
        lines = ["\n  Learn NTFS by exploring your own disk:\n"]
        for num, title, _ in LESSONS:
            lines.append(f"  [bold cyan]{num}[/] | {title}")
        lines.append(f"  [bold cyan]a[/] | Run all lessons")
        lines.append(f"  [bold cyan]q[/] | Quit")
        lines.append("")
        console.print(Panel("\n".join(lines), title="Lessons",
                            border_style="magenta"))

        choices = [num for num, _, _ in LESSONS] + ["a", "q"]
        choice = Prompt.ask("[bold]Choose lesson", choices=choices,
                            default="q")

        if choice == "q":
            break
        elif choice == "a":
            for _, _, mod in LESSONS:
                mod.run(drive_letter=drive, animate=animate)
        else:
            for num, _, mod in LESSONS:
                if num == choice:
                    mod.run(drive_letter=drive, animate=animate)
                    break


def main():
    parser = argparse.ArgumentParser(description="NTFS Learning Lab")
    parser.add_argument("--lesson", type=int, choices=range(1, 7),
                        help="Run specific lesson (1-6)")
    parser.add_argument("--drive", default="C",
                        help="Drive letter to analyze (default: C)")
    parser.add_argument("--animate", action="store_true",
                        help="Enable cinematic effects")
    parser.add_argument("--all", action="store_true",
                        help="Run all lessons sequentially")
    args = parser.parse_args()

    if args.all:
        for _, _, mod in LESSONS:
            mod.run(drive_letter=args.drive, animate=args.animate)
    elif args.lesson:
        _, _, mod = LESSONS[args.lesson - 1]
        mod.run(drive_letter=args.drive, animate=args.animate)
    else:
        interactive(args.drive, args.animate)


if __name__ == "__main__":
    main()
