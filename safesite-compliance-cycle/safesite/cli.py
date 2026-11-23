"""Command line: ``python -m safesite <command>``.

    init     create the consortium (12 facilities, 4 coordinators)
    plan     assignments and the deadline calendar for a quarter
    cycle    as of a date: take in returns, check them, draft the reminders that date calls for
    report   build the two Word reports and the QA pack; --approve ROLE writes the finals
    demo     the quarter from the first reminder to the approved finals
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date, timedelta
from pathlib import Path

from . import synth
from .cycle import CycleReport, Workspace, plan_quarter, run_cycle
from .reports import produce

QUARTER, DUE = synth.QUARTER, synth.DUE


def arrivals() -> dict[str, date]:
    out = {}
    for fid, (day, _, fixed_on) in synth.SCHEDULE.items():
        out[f"{fid}_v1.xlsx"] = day
        if fixed_on:
            out[f"{fid}_v2.xlsx"] = fixed_on
    return out


def write_calendar(ws: Workspace, rows) -> Path:
    path = ws.working / QUARTER / "calendar.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["assignment", "facility", "coordinator", "reminder T-14", "reminder T-3", "due"])
        for r in rows:
            due = date.fromisoformat(r["due_at"])
            w.writerow([r["assignment_id"], r["name"], r["role"], due - timedelta(days=14), due - timedelta(days=3),
                        due])
    return path


def _print_cycle(c: CycleReport) -> None:
    if c.received:
        print(f"  received: {', '.join(c.received)}")
    if c.accepted:
        print(f"  accepted: {', '.join(c.accepted)}")
    for fid, problems in c.corrections:
        print(f"  correction requested from {fid}: {problems[0]}" + (f" (+{len(problems) - 1} more)"
                                                                    if len(problems) > 1 else ""))
    kinds: dict[str, list[str]] = {}
    for fid, kind in c.reminders:
        kinds.setdefault(kind, []).append(fid)
    for kind, fids in kinds.items():
        print(f"  {kind} drafts: {', '.join(fids)}")
    print("  states: " + ", ".join(f"{k} {v}" for k, v in sorted(c.states.items())))


def run_demo(out: Path, seed: int) -> int:
    if out.exists():
        for p in out.rglob("*"):
            if p.is_file():
                p.chmod(0o666)
        shutil.rmtree(out)
    ws = Workspace(out)
    con = ws.open()
    facilities = synth.build_consortium(con, seed)

    print(f"\n== 1. Plan {QUARTER}: 12 facilities, 4 coordinators, returns due {DUE}")
    rows = plan_quarter(con, QUARTER, DUE)
    con.close()
    print(f"  {len(rows)} assignments; calendar: {write_calendar(ws, rows).relative_to(out).as_posix()}")

    for n, (day, title) in enumerate([(date(2026, 12, 1), "Two weeks out: first returns arrive and are checked"),
                                      (date(2026, 12, 12), "Three days out: corrections come back"),
                                      (date(2026, 12, 18), "Past the deadline: escalate what is missing")],
                                     start=2):
        print(f"\n== {n}. {title} (as of {day})")
        synth.deliver(ws.submissions, facilities, day, seed)
        _print_cycle(run_cycle(ws, QUARTER, day, arrivals()))
        if n == 3:
            again = run_cycle(ws, QUARTER, day, arrivals())
            print(f"  same day, run again: {len(again.reminders)} new drafts (reminders are never duplicated)")

    r = produce(ws, QUARTER, approve_as="safety lead")
    print(f"  final reports: {r.verdict} - {', '.join(r.blockers)}")
    print(f"  drafts instead: {', '.join(r.drafts)}")

    print("\n== 5. Late returns arrive; the safety lead approves")
    synth.deliver(ws.submissions, facilities, date(2026, 12, 20), seed)
    _print_cycle(run_cycle(ws, QUARTER, date(2026, 12, 20), arrivals()))
    r = produce(ws, QUARTER, approve_as="safety lead")
    print(f"  reports: {r.verdict}: {', '.join(r.finals)}")
    r = produce(ws, QUARTER, approve_as="safety lead")
    print(f"  approve again: {r.verdict}")

    print("\n== 6. Folders kept apart")
    for folder in (ws.working, ws.qa, ws.final, ws.outbox):
        files = sorted(p.name for p in (folder / QUARTER).iterdir())
        print(f"  {folder.name}/{QUARTER}: {len(files)} file(s), e.g. {files[0]}")
    print("  Nothing is emailed: every reminder is an .eml draft in outbox/.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="safesite", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "plan", "cycle", "report"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        if name == "cycle":
            p.add_argument("--as-of", type=date.fromisoformat, required=True)
        if name == "report":
            p.add_argument("--approve", metavar="ROLE")
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        con = ws.open()
        print(f"{len(synth.build_consortium(con))} facilities")
        con.close()
        return 0
    if args.command == "plan":
        con = ws.open()
        rows = plan_quarter(con, QUARTER, DUE)
        con.close()
        print(f"{len(rows)} assignments; calendar {write_calendar(ws, rows)}")
        return 0
    if args.command == "cycle":
        _print_cycle(run_cycle(ws, QUARTER, args.as_of))
        return 0
    r = produce(ws, QUARTER, approve_as=args.approve)
    print(r.verdict, r.blockers or "")
    return 0 if not r.blockers else 1
