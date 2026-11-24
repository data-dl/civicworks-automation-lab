"""Command line: ``python -m ledgerguard <command>``.

    init     write the cooperative's three synthetic sources
    run      one day's QA run (--date, --desk-mode normal|empty|renamed-column|truncated)
    restore  put an archived day's verified outputs back as current
    demo     four days, including the export failures, then a restore
"""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import sources
from .jobs import DayResult, Workspace, restore, run_day
from .runkit import scene as announce


@dataclass
class Scene:
    number: int
    title: str
    run: Callable[[], None]


def _print(day: DayResult, show_exceptions: bool = False) -> None:
    for j in day.jobs:
        mark = "ok" if j.state == "verified" else "QUARANTINED"
        print(f"  {j.code:24} {j.adapter:10} {mark:11} {j.observed:>3}/{j.expected:<3} rows  "
              f"{len(j.exceptions)} exceptions" + (f"  - {j.reason}" if j.reason else ""))
        if show_exceptions:
            for e in j.exceptions:
                print(f"      {e['detail']}")
    if day.carried_forward:
        print(f"  kept yesterday's verified file for: {', '.join(day.carried_forward)} (marked stale)")
    if day.archived:
        print(f"  the previous verified set moved to archive/{day.archived}/ with its SHA-256 manifest")


def prepare(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)


def scenes(out: Path, seed: int = 20261123) -> list[Scene]:
    ws = Workspace(out)

    def s1():
        info = sources.generate(ws.sources, seed)
        print(f"  registry.sqlite: {info['equipment']} equipment items; roster.csv: {info['technicians']} technicians;"
              f" authorizations.csv: {info['authorizations']} authorisations; plus the desk app's Export button")
        print("  planted: a blank serial, a missing service date, one serial under two classes, a technician "
              "active with every authorisation lapsed, a depot class nobody may service")

    def s2():
        _print(run_day(ws, date(2026, 11, 23)), show_exceptions=True)
        print("  published as one set: current/ holds four verified files, exceptions.xlsx and dashboard.html")

    def s3():
        print("  the desk app says 'Export complete' - but wrote only the header row")
        _print(run_day(ws, date(2026, 11, 24), desk_mode="empty"))

    def s4():
        print("  after a desk app update, a column is renamed in its export")
        _print(run_day(ws, date(2026, 11, 25), desk_mode="renamed-column"))

    def s5():
        _print(run_day(ws, date(2026, 11, 26)))
        print(f"  archive/ now holds: {', '.join(sorted(p.name for p in ws.archive.iterdir()))}")

    def s6():
        victim = ws.archive / "2026-11-25" / "category_overlaps.csv"
        victim.write_text(victim.read_text(encoding="utf-8") + "SNFAKE,EXC\n", encoding="utf-8")
        ok, note = restore(ws, "2026-11-25")
        print(f"  restore 2026-11-25 after someone edited a file in it: {'OK' if ok else 'REFUSED'} - {note}")
        ok, note = restore(ws, "2026-11-23")
        print(f"  restore 2026-11-23: {'OK' if ok else 'REFUSED'} - {note}")

    return [Scene(1, "Three source systems and an old desktop export, with data problems planted", s1),
            Scene(2, "Day 1: all four exports proven usable, then checked for exceptions", s2),
            Scene(3, "Day 2: the desktop export 'succeeds' with no rows", s3),
            Scene(4, "Day 3: the export's columns change", s4),
            Scene(5, "Day 4: healthy again; yesterday's set is archived before it is replaced", s5),
            Scene(6, "Restore: a tampered archive is refused, an intact one comes back", s6)]


def run_demo(out: Path, seed: int) -> int:
    prepare(out)
    for sc in scenes(out, seed):
        announce(sc.number, sc.title)
        sc.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledgerguard", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "run", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        if name == "init":
            p.add_argument("--seed", type=int, default=20261123)
        if name == "run":
            p.add_argument("--date", type=date.fromisoformat, default=sources.RUN_DATE)
            p.add_argument("--desk-mode", choices=sources.DeskAppExport.MODES, default="normal")
        if name == "restore":
            p.add_argument("--day", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        print(sources.generate(ws.sources, args.seed))
        return 0
    if args.command == "run":
        day = run_day(ws, args.date, args.desk_mode)
        _print(day, show_exceptions=True)
        return 0 if all(j.state == "verified" for j in day.jobs) else 1
    ok, note = restore(ws, args.day)
    print(note)
    return 0 if ok else 1
