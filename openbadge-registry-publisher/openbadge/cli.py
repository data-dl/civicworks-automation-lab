"""Command line: ``python -m openbadge <command>``.

    init      create the workspace database and fill it with synthetic learners and badges
    release   snapshot -> validate -> publish -> verify over HTTP -> switch the pointer
    consume   act as the outside catalogue: fetch latest, check it, accept or reject
    rollback  point consumers back at an earlier verified release
    status    one line per release
    demo      the whole story on a fresh workspace, including the failures
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from . import synth
from .release import ReleaseResult, Workspace, consume, release, rollback, status_rows
from .runkit import scene as announce

AS_OF = date(2026, 11, 23)


def _print_release(r: ReleaseResult) -> None:
    print(f"  release {r.release_id}: {r.verdict}  ({r.record_count} badges, sha256 {r.sha256[:12]})")
    for f in r.findings:
        mark = "x" if f.severity == "blocking" else "-"
        print(f"    [{mark}] {f.rule}: {f.detail}")
    for note in r.notes:
        print(f"    {note}")


def _print_status(ws: Workspace) -> None:
    print(f"  {'release':8} {'badges':>6}  {'technical':14} {'consumer':12} {'file':8}")
    for row in status_rows(ws):
        records = "" if row["records"] is None else row["records"]
        print(f"  {row['release']:8} {records:>6}  {row['technical']:14} {row['consumer']:12} "
              f"{row['file']:8} {row['live']}")


def scene(n: int, title: str) -> None:
    announce(n, title)


def run_demo(out: Path, seed: int) -> int:
    if out.exists():
        shutil.rmtree(out)
    ws = Workspace(out)
    con = ws.open()

    scene(1, "Seed a synthetic academy")
    info = synth.seed_database(con, seed=seed)
    con.close()
    print(f"  {info['learners']} learners, {info['badges']} badges, 12 badge types (seed {seed})")

    scene(2, "First release: validate, publish, verify over HTTP, then move the pointer")
    _print_release(release(ws, AS_OF, seed=seed))
    c = consume(ws)
    print(f"  catalogue import: {c.verdict} ({c.reason})")

    scene(3, "Bad data arrives: a duplicated badge and an impossible expiry date")
    con = ws.open()
    dup, bad = synth.plant_duplicate(con), synth.plant_invalid_date(con)
    con.close()
    print(f"  planted: duplicate {dup}, invalid date on {bad}")
    _print_release(release(ws, AS_OF, seed=seed))

    scene(4, "Steward fixes the data; this time the upload is cut off half way")
    con = ws.open()
    print(f"  repaired: {synth.repair_planted(con)}; new approvals: {synth.issue_new_badges(con, seed + 1)}")
    con.close()
    _print_release(release(ws, AS_OF, inject="corrupt-after-write", seed=seed))

    scene(5, "Re-run the release; the catalogue imports it a day later")
    _print_release(release(ws, AS_OF, seed=seed))
    c = consume(ws, delayed=True)
    print(f"  catalogue import: {c.verdict} ({c.reason})")
    c = consume(ws, delayed=True)
    print(f"  catalogue import (next day): {c.verdict} ({c.reason})")

    scene(6, "Roll back: a release that never verified is refused, the last good one is accepted")
    r = rollback(ws, to="R0003")
    print(f"  rollback to R0003: {'OK' if r.ok else 'REFUSED'} - {r.reason}")
    r = rollback(ws)
    print(f"  rollback to previous: {'OK' if r.ok else 'REFUSED'} - {r.reason}")

    scene(7, "Release history")
    _print_status(ws)
    print(f"\n  evidence: {out.as_posix()}/runs/<release>/manifest.json, tickets in {out.as_posix()}/tickets/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openbadge", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "release", "consume", "rollback", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        if name == "init":
            p.add_argument("--seed", type=int, default=20261123)
            p.add_argument("--learners", type=int, default=120)
        if name == "release":
            p.add_argument("--as-of", type=date.fromisoformat, default=AS_OF)
            p.add_argument("--dry-run", action="store_true", help="check only; publish nothing")
            p.add_argument("--accept-drop", action="store_true", help="allow more than 20%% of badges to leave")
        if name == "consume":
            p.add_argument("--delayed", action="store_true", help="the first check only queues the import")
        if name == "rollback":
            p.add_argument("--to", help="release id; default: the latest earlier verified release")
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)

    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        if ws.db.exists():
            print(f"{ws.db} already exists; refusing to reseed", file=sys.stderr)
            return 2
        con = ws.open()
        print(synth.seed_database(con, seed=args.seed, learners=args.learners))
        con.close()
        return 0
    if args.command == "release":
        r = release(ws, args.as_of, apply=not args.dry_run, accept_drop=args.accept_drop)
        _print_release(r)
        return 0 if r.verdict in ("PUBLISHED", "DRY-RUN") else 1
    if args.command == "consume":
        c = consume(ws, delayed=args.delayed)
        print(f"{c.release_id}: {c.verdict} ({c.reason})" + (f"; ticket {c.ticket}" if c.ticket else ""))
        return 0 if c.verdict != "rejected" else 1
    if args.command == "rollback":
        r = rollback(ws, args.to)
        print(("OK: " if r.ok else "REFUSED: ") + r.reason)
        return 0 if r.ok else 1
    _print_status(ws)
    return 0
