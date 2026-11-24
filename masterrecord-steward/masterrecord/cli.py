"""Command line: ``python -m masterrecord <command>``.

    init     build the fictional master workbook and this month's three feeds
    propose  resolve every field by the precedence matrix; write the review queue and a decisions template
    apply    write approved decisions into the master (dry run unless --apply)
    demo     the whole stewardship cycle on a fresh workspace
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date
from pathlib import Path

from . import synth
from .apply import ApplyResult, apply_decisions
from .runkit import scene as announce
from .steward import ProposeResult, Workspace, propose

TODAY = date(2026, 11, 23)


def init(ws: Workspace, seed: int) -> None:
    rows = synth.build_master(ws.master, seed)
    synth.write_feeds(ws.feeds / synth.CYCLE, rows)


def _print_propose(r: ProposeResult) -> None:
    print(f"  {r.agreed} field values agree with the master; {r.duplicates_ignored} duplicate assertions ignored")
    print(f"  {len(r.changes)} changes to approve:")
    for c in r.changes:
        print(f"    {c['proposal_id']}: {c['current'] or '(blank)'} -> {c['proposed']}  [{c['explanation']}]")
    print(f"  {len(r.holds)} holds for a person:")
    for h in r.holds:
        print(f"    {h['proposal_id']}: {h['explanation']}")
    for x in r.excluded:
        print(f"  excluded {x['entity_id']}: {x['explanation']}")


def _print_apply(r: ApplyResult) -> None:
    for e in r.errors:
        print(f"    error: {e}")
    for p in r.planned:
        verb = "would write" if r.mode == "dry-run" else "wrote"
        print(f"    {verb} {p['entity']} {p['field']}: {p['old'] or '(blank)'} -> {p['new']}")
    if r.already_applied:
        print(f"    already applied, skipped: {len(r.already_applied)}")
    if r.skipped:
        print(f"    no decision yet: {', '.join(r.skipped)}")
    if r.sheet:
        print(f"    new tab '{r.sheet}'; backup {r.backup}; {r.preserved_cells} existing cells checked unchanged")


def write_demo_decisions(path: Path, proposed: ProposeResult) -> Path:
    choices = {"H-GJF-0008-inspection_zone": ("choose", "Z4", "newer inspection on 18 Nov supersedes 12 Nov"),
               "H-GJF-0011-workshop_type": ("choose", "finishing", "renewed contract lists finishing as main trade")}
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["proposal_id", "resolution", "value", "approver_role", "rationale"])
        for c in proposed.changes + proposed.excluded:
            w.writerow([c["proposal_id"], "approve", c["proposed"], "guild registrar", "matches source evidence"])
        for h in proposed.holds:
            resolution, value, why = choices.get(h["proposal_id"], ("", "", ""))
            w.writerow([h["proposal_id"], resolution, value, "guild registrar" if resolution else "", why])
    return path


def run_demo(out: Path, seed: int) -> int:
    if out.exists():
        shutil.rmtree(out)
    ws = Workspace(out)
    announce(1, "A guild master workbook and three feeds that disagree")
    init(ws, seed)
    print(f"  master: 30 workshops, an earlier Changes tab, reference rows at row {synth.REFERENCE_ROW}")
    print("  feeds: registry (authoritative), contract, site inspections")

    announce(2, "Propose: resolve every field by the precedence matrix")
    proposed = propose(ws, synth.CYCLE)
    _print_propose(proposed)
    print(f"  review queue: {Path(proposed.review_file).relative_to(out).as_posix()}")

    announce(3, "The registrar decides: approve the changes, settle two holds, leave two for later")
    decisions = write_demo_decisions(ws.review / f"decisions_{synth.CYCLE}_signed.csv", proposed)
    print(f"  decisions file: {decisions.relative_to(out).as_posix()}")

    announce(4, "Dry run: what would be written")
    _print_apply(apply_decisions(ws, decisions, today=TODAY))

    announce(5, "Apply: backup, write, prove nothing else moved")
    _print_apply(apply_decisions(ws, decisions, apply=True, today=TODAY))

    announce(6, "Apply the same decisions again")
    r = apply_decisions(ws, decisions, apply=True, today=TODAY)
    print(f"  {len(r.planned)} writes; {len(r.already_applied)} decisions already applied - nothing changed")

    announce(7, "Next proposal run: only the undecided holds remain")
    again = propose(ws, synth.CYCLE)
    print(f"  changes {len(again.changes)}, holds {len(again.holds)}: "
          + ", ".join(h["proposal_id"] for h in again.holds))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="masterrecord", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "propose", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        if name == "init":
            p.add_argument("--seed", type=int, default=20261123)
        if name == "apply":
            p.add_argument("--decisions", type=Path, required=True)
            p.add_argument("--apply", action="store_true", help="write to the master (default: dry run)")
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        init(ws, args.seed)
        return 0
    if args.command == "propose":
        _print_propose(propose(ws, synth.CYCLE))
        return 0
    r = apply_decisions(ws, args.decisions, apply=args.apply)
    _print_apply(r)
    return 1 if r.errors else 0
