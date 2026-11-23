"""Command line: ``python -m regional <command>``.

    init    create the network and the synthetic submissions for 2026Q2 (clean) and 2026Q3 (with defects)
    run     process one quarter; --approve ROLE to approve it if nothing blocks
    demo    the whole story on a fresh workspace
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from . import synth
from .pipeline import QuarterResult, Workspace, run_quarter


def _print(r: QuarterResult) -> None:
    print(f"  {r.quarter}: {r.verdict}  (usable submissions {r.accepted} of {r.expected})")
    for f in r.findings:
        print(f"    [{'x' if f.severity == 'blocking' else '-'}] {f.rule}: {f.detail}")
    if r.outputs:
        print(f"    built: {', '.join(r.outputs)}")
    if r.approved_folder:
        print(f"    approved copies (read-only): {Path(r.approved_folder).name}/")


def init(ws: Workspace, seed: int) -> dict:
    con = ws.open()
    venues = synth.build_network(con, seed)
    con.close()
    synth.write_quarter(ws.inbox, venues, "2026Q2", seed)
    planted = synth.write_quarter(ws.inbox, venues, "2026Q3", seed, defects=True)
    return {"venues": venues, "planted": planted}


def run_demo(out: Path, seed: int) -> int:
    if out.exists():
        for p in out.rglob("*"):
            if p.is_file():
                p.chmod(0o666)  # approved copies are read-only
        shutil.rmtree(out)
    ws = Workspace(out)

    print("\n== 1. A fictional arts network: 4 regions, 16 venues, two service tiers")
    info = init(ws, seed)
    print(f"  {len(info['venues'])} venues; 2026Q2 submissions clean; 2026Q3 has planted problems:")
    for kind, where in info["planted"].items():
        print(f"    {kind}: {where}")

    print("\n== 2. Last quarter: checks pass, the program director approves it")
    _print(run_quarter(ws, "2026Q2", approve_as="program director", seed=seed))

    print("\n== 3. This quarter: draft packs are built, but approval is blocked")
    _print(run_quarter(ws, "2026Q3", approve_as="program director", seed=seed))

    print("\n== 4. Reminders went out; the late and corrected files arrive")
    for name in synth.write_late_files(ws.inbox, info["venues"], "2026Q3", seed):
        print(f"    received {name}")
    _print(run_quarter(ws, "2026Q3", approve_as="program director", seed=seed))

    print("\n== 5. Someone re-runs approval: the approved quarter is not replaced")
    _print(run_quarter(ws, "2026Q3", approve_as="program director", seed=seed))

    print("\n== 6. What was produced")
    for folder in (ws.approved / "2026Q3" / "v1", ws.outbox / "2026Q3"):
        print(f"  {folder.relative_to(out).as_posix()}/")
        for p in sorted(folder.iterdir()):
            print(f"    {p.name}")
    print("  Drafts are never sent: the outbox holds .eml files for a person to review.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regional", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--workspace", type=Path, default=Path("build/workspace"))
    p_init.add_argument("--seed", type=int, default=20261123)
    p_run = sub.add_parser("run")
    p_run.add_argument("--workspace", type=Path, default=Path("build/workspace"))
    p_run.add_argument("--quarter", required=True, help="e.g. 2026Q3")
    p_run.add_argument("--approve", metavar="ROLE", help="approve as this role if nothing blocks")
    p_run.add_argument("--new-version", action="store_true", help="approve a revision of an approved quarter")
    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--out", type=Path, default=Path("build/demo"))
    p_demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)

    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "init":
        if ws.db.exists():
            print("workspace already initialised")
            return 2
        info = init(ws, args.seed)
        print(f"{len(info['venues'])} venues; planted in 2026Q3: {info['planted']}")
        return 0
    r = run_quarter(ws, args.quarter, approve_as=args.approve, new_version=args.new_version)
    _print(r)
    return 0 if not r.blocking else 1
