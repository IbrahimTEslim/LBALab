"""
Animate — Cinematic visual effects for NTFS disk operations.

All timings are controlled by EFFECT_DURATION (seconds).
Change it once here to speed up or slow down every effect globally.

Effects:
- hex_reveal: bytes stream in like data arriving from disk
- typewriter: text appears character by character
- decode_reveal: random chars settle into real values
- panel_build: panel content appears line by line
- scan_line: a scanning line sweeps across text
"""
import os
import sys
import time
import random
import string

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(width=min(Console().width or 100, 100))

# ── Central timing config ─────────────────────────────────────
# Every effect scales from this single value (in seconds).
# 0.5 = snappy, 1.0 = cinematic, 2.0 = dramatic
EFFECT_DURATION = 0.5


def _noop(*_a, **_kw):
    """Placeholder when animations are disabled."""
    pass


def hex_reveal(data, title="Reading", offset=0, enabled=False):
    """Bytes stream into a hex dump like data arriving off disk."""
    bpr = 16 if console.width >= 100 else 8
    rows = []
    for i in range(0, min(len(data), 256), bpr):
        chunk = data[i:i + bpr]
        rows.append((offset + i, chunk))

    if not enabled or not rows:
        return

    total = sum(len(c) for _, c in rows)
    delay = EFFECT_DURATION / max(total, 1)
    pad = bpr * 3 - 1

    built = []
    with Live(Panel("", title=title, border_style="blue"), console=console,
              refresh_per_second=30) as live:
        for addr, chunk in rows:
            for j in range(1, len(chunk) + 1):
                partial = chunk[:j]
                h = " ".join(f"{b:02x}" for b in partial)
                a = "".join(chr(b) if 32 <= b <= 126 else "." for b in partial)
                cur = f"  [dim]{addr:08x}:[/] [green]{h:<{pad}}[/] [dim]|[/] {a}"
                lines = built + [cur]
                live.update(Panel("\n".join(lines), title=title,
                                 border_style="blue"))
                time.sleep(delay)
            # Finalize row (green -> normal)
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            built.append(f"  [dim]{addr:08x}:[/] {h:<{pad}} [dim]|[/] {a}")

        live.update(Panel("\n".join(built), title=title, border_style="blue"))


def decode_reveal(final_text, title="Decoding", style="cyan",
                  enabled=False):
    """Random characters settle into the real text, like decryption."""
    if not enabled:
        return

    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    length = len(final_text)
    steps = max(8, int(EFFECT_DURATION / 0.06))
    locked = [False] * length

    with Live(Panel("", title=title, border_style=style), console=console,
              refresh_per_second=30) as live:
        for step in range(steps):
            frac = step / steps
            buf = []
            for i, ch in enumerate(final_text):
                if ch in (" ", "\n"):
                    buf.append(ch)
                    locked[i] = True
                elif locked[i]:
                    buf.append(ch)
                elif random.random() < frac:
                    buf.append(ch)
                    locked[i] = True
                else:
                    buf.append(f"[green]{random.choice(chars)}[/]")
            live.update(Panel("".join(buf), title=title, border_style=style))
            time.sleep(EFFECT_DURATION / steps)

        live.update(Panel(final_text, title=title, border_style=style))


def panel_build(lines, title="", style="blue", enabled=False):
    """Panel content appears line by line from top."""
    if not enabled or not lines:
        return

    delay = EFFECT_DURATION / max(len(lines), 1)

    with Live(Panel("", title=title, border_style=style), console=console,
              refresh_per_second=20) as live:
        shown = []
        for line in lines:
            shown.append(line)
            live.update(Panel("\n".join(shown), title=title,
                              border_style=style))
            time.sleep(delay)


def typewriter(text, style="bold cyan", enabled=False):
    """Text appears character by character on one line."""
    if not enabled:
        console.print(f"[{style}]{text}[/]")
        return

    delay = EFFECT_DURATION / max(len(text), 1)
    with Live(Text(""), console=console, refresh_per_second=30) as live:
        for i in range(1, len(text) + 1):
            t = Text(text[:i])
            t.stylize(style)
            live.update(t)
            time.sleep(delay)


def scan_line(text, title="Scanning", style="yellow", enabled=False):
    """A highlight sweeps across the text left to right."""
    if not enabled:
        return

    length = len(text)
    steps = max(length, 10)
    delay = EFFECT_DURATION / steps

    with Live(Panel("", title=title, border_style=style), console=console,
              refresh_per_second=30) as live:
        for pos in range(length + 1):
            before = text[:pos]
            highlight = text[pos:pos + 1] if pos < length else ""
            after = text[pos + 1:] if pos + 1 < length else ""
            display = f"{before}[black on green]{highlight}[/]{after}"
            live.update(Panel(display, title=title, border_style=style))
            time.sleep(delay)

        live.update(Panel(text, title=title, border_style=style))


def flash_result(text, style="bold green", enabled=False):
    """Flash a result message — blinks twice then stays."""
    if not enabled:
        console.print(f"[{style}]{text}[/]")
        return

    blink_time = EFFECT_DURATION / 4
    with Live(Text(""), console=console, refresh_per_second=20) as live:
        for _ in range(2):
            live.update(Text(""))
            time.sleep(blink_time)
            t = Text(text)
            t.stylize(style)
            live.update(t)
            time.sleep(blink_time)
