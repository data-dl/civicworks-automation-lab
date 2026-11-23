"""Command line: ``python -m reconcilehub <command>``.

    init       write this month's three synthetic inputs
    reconcile  compare them; print actions and held cases (changes nothing)
    decide     record decisions for held cases from a CSV (case_id, disposition, reviewer)
    commit     approve: snapshot + import workbook + change report (blocked while anything is held)
    demo       the month from raw inputs to an approved import, and what happens on re-runs
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from . import synth
from .commit import commit
from .reconcile import Recon, Workspace, reconcile, record_decisions


def _print(r: Recon) -> None:
    counts: dict[str, int] = {}
    for a in r.actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    print(f"  unchanged {r.unchanged}; ids normalised {r.normalised_ids}; actions: "
          + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"))
    for a in r.actions:
        print(f"    {a['action']:11} {a['member_id']} {a['name']}: {a['reason']}")
    for c in r.cases:
        print(f"    case [{c.disposition}] {c.kind} ({c.confidence:.0%}): {c.detail}")
    for n in r.notes:
        print(f"    note: {n}")


def run_demo(out: Path, seed: int) -> int:
    if out.exists():
        shutil.rmtree(out)
    ws = Workspace(out)
    cycle = synth.CYCLE
    print("\n== 1. This month's inputs: access-system roster, last month's approvals, new registrations")
    info = synth.build_inputs(ws.inputs, seed)
    for kind, where in info["planted"].items():
        print(f"  planted {kind}: {where}")

    print("\n== 2. Reconcile: exact matches decided, everything else held")
    r = reconcile(ws, cycle)
    _print(r)

    print("\n== 3. Try to approve before review")
    res = commit(ws, cycle, "membership lead")
    print(f"  {res.verdict}; draft to space admins: {', '.join(res.drafts)}")

    print("\n== 4. A reviewer decides the held cases")
    decisions = ws.inputs / cycle / "decisions.csv"
    choice = {"possible-id-change": "same-person", "missing-id": "same-person", "possible-duplicate": "same-person"}
    with decisions.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["case_id", "disposition", "reviewer"])
        for c in r.held:
            w.writerow([c.case_id, choice.get(c.kind, "exclude"), "membership lead"])
            print(f"    {c.case_id} -> {choice.get(c.kind, 'exclude')}")
    problems = record_decisions(ws, cycle, decisions)
    print(f"  recorded ({len(problems)} problems)")
    _print(reconcile(ws, cycle))

    print("\n== 5. Approve")
    res = commit(ws, cycle, "membership lead")
    print(f"  {res.verdict}: {', '.join(res.files)}")

    print("\n== 6. Run it again: same inputs, same decisions")
    print(f"  {commit(ws, cycle, 'membership lead').verdict}")

    print("\n== 7. A late registration arrives after approval")
    synth.late_registration(ws.inputs)
    print(f"  {commit(ws, cycle, 'membership lead').verdict}")
    res = commit(ws, cycle, "membership lead", supersede="late registration REG-2611-04")
    print(f"  with --supersede: {res.verdict}: {', '.join(res.files)}")
    print(f"  v1 is still in {ws.snapshots.relative_to(out).as_posix()}/{cycle}/v1/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reconcilehub", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "reconcile", "decide", "commit"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        p.add_argument("--cycle", default=synth.CYCLE)
        if name == "decide":
            p.add_argument("--decisions", type=Path, required=True)
        if name == "commit":
            p.add_argument("--approve", metavar="ROLE", required=True)
            p.add_argument("--supersede", metavar="REASON")
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        print(synth.build_inputs(ws.inputs)["planted"])
        return 0
    if args.command == "reconcile":
        _print(reconcile(ws, args.cycle))
        return 0
    if args.command == "decide":
        problems = record_decisions(ws, args.cycle, args.decisions)
        print("\n".join(problems) or "recorded")
        return 1 if problems else 0
    res = commit(ws, args.cycle, args.approve, args.supersede)
    print(res.verdict, res.files or res.drafts)
    return 0 if res.verdict.startswith(("APPROVED", "NOTHING NEW")) else 1
