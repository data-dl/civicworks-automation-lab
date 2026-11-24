"""Command line: ``python -m opspilot <command>``.

    tools     list the registry: every action OpsPilot may take, with inputs and effect
    plan      show the dependency order for a goal
    run       start a goal (or --resume RUN_ID); publish steps wait for approval
    approve   a person approves one publish step of one run (prints the token)
    status    write the read-only status page
    env       what this machine can do
    demo      every behaviour, on a fresh control room
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sqlite3
import stat
import sys
from pathlib import Path

from . import dashboard
from .executor import OpsPilot, RunSummary, SimulatedCrash
from .registry import LanguageModelPlanner, Refused
from .runkit import scene as announce


def _print_run(s: RunSummary) -> None:
    for o in s.outcomes:
        print(f"    {o.step:17} {o.status:18} {o.note}")
    print(f"  run {s.run_id}: {s.state.upper()}")
    print(f"  next: {s.next_action}")


def environment(root: Path) -> dict:
    headless = os.environ.get("CI") == "true" or (platform.system() != "Windows" and not os.environ.get("DISPLAY"))
    probe = root / ".write-probe"
    try:
        probe.write_text("x")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    return {"profile": "headless CI" if headless else "desktop", "os": platform.system(),
            "python": platform.python_version(), "workspace writable": writable,
            "desktop automation": "not used by any registered tool"}


def _clear(out: Path) -> None:
    if out.exists():
        for p in out.rglob("*"):
            if p.is_file():
                p.chmod(stat.S_IWRITE | stat.S_IREAD)
        shutil.rmtree(out)


def run_demo(out: Path) -> int:
    _clear(out)
    ops = OpsPilot(out)

    announce(1, "The registry: the only actions OpsPilot can take")
    for name, t in ops.tools.items():
        print(f"  {name:24} {t.effect:8} inputs: {', '.join(f'{k}:{v}' for k, v in t.inputs.items())}")
    print(f"  environment: {environment(out)}")

    announce(2, "Plan 'publish-cycle' with the rules planner")
    for n, s in enumerate(ops.plan("publish-cycle"), start=1):
        after = f" (after {', '.join(s.after)})" if s.after else ""
        print(f"  {n}. {s.id:17} {s.tool}{after}")

    announce(3, "Run it: write steps proceed, publish steps wait for a person")
    run_id = ops.start("publish-cycle")
    _print_run(ops.run(run_id))

    announce(4, "A person approves the two publish steps")
    for step, role in (("badge-release", "release manager"), ("regional-approve", "program director")):
        print(f"  {ops.approve(run_id, step, role)}: {step} approved by the {role}")

    announce(5, "Resume - and the machine stops right after the badge release")
    try:
        ops.run(run_id, crash_after="badge-release")
    except SimulatedCrash as exc:
        print(f"  !! {exc}; run marked interrupted")

    announce(6, "Resume again: verified checkpoints are skipped, the rest finishes")
    _print_run(ops.run(run_id))

    announce(7, "A second goal: the roster project's own checks stop it")
    roster = ops.start("roster-cycle")
    ops.approve(roster, "roster-commit", "membership lead")
    _print_run(ops.run(roster))

    announce(8, "Requests OpsPilot refuses (each one is logged)")
    attempts = [("an unregistered command", lambda: ops.request("shell.exec", command="del /q *")),
                ("a path outside the workspaces", lambda: ops.request("openbadge.init", workspace="../../Windows")),
                ("a publish outside a planned, approved run", lambda: ops.request("openbadge.release",
                                                                                   workspace="openbadge")),
                ("a language-model plan", lambda: ops.plan("publish-cycle", planner=LanguageModelPlanner())),
                ("approving a step that does not publish", lambda: ops.approve(run_id, "master-init", "anyone"))]
    for label, attempt in attempts:
        try:
            attempt()
            print(f"  {label}: ALLOWED (unexpected)")
        except Refused as exc:
            print(f"  {label}: REFUSED - {exc}")
    try:
        ops.con.execute("DELETE FROM event_log")
    except sqlite3.DatabaseError as exc:
        print(f"  erasing the event log: REFUSED by the database - {exc}")

    announce(9, "Read-only status page")
    page = dashboard.build(ops)
    events = ops.con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    print(f"  {page.relative_to(out).as_posix()} ({events} events, 2 runs); handoff notes in logs/<run>/HANDOFF.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("build/control"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools")
    sub.add_parser("env")
    sub.add_parser("status")
    p = sub.add_parser("plan")
    p.add_argument("goal")
    r = sub.add_parser("run")
    r.add_argument("goal", nargs="?")
    r.add_argument("--resume", metavar="RUN_ID")
    a = sub.add_parser("approve")
    a.add_argument("--run", required=True)
    a.add_argument("--step", required=True)
    a.add_argument("--role", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--out", type=Path, default=Path("build/demo"))
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out)
    ops = OpsPilot(args.root)
    try:
        if args.command == "tools":
            for name, t in ops.tools.items():
                print(f"{name:24} {t.effect:8} {t.inputs}")
        elif args.command == "env":
            print(environment(args.root))
        elif args.command == "status":
            print(dashboard.build(ops))
        elif args.command == "plan":
            for s in ops.plan(args.goal):
                print(s.id, s.tool, s.after)
        elif args.command == "approve":
            print(ops.approve(args.run, args.step, args.role))
        else:
            run_id = args.resume or ops.start(args.goal)
            summary = ops.run(run_id)
            _print_run(summary)
            return 0 if summary.state == "complete" else 1
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    return 0
