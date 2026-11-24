"""Command line: ``python -m atlas <command>``.

    generate  write this period's four synthetic source catalogs (--with-problems plants one of each)
    run       check -> freeze -> render -> verify -> publish (--approve ROLE, --resume, --crash-after STAGE)
    rollback  point readers back at an earlier published period
    status    releases and which one is current
    demo      the whole story, scene by scene
"""

from __future__ import annotations

import argparse
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import synth
from .release import RunResult, SimulatedCrash, current, rollback, run
from .runkit import scene as announce
from .stages import Workspace


@dataclass
class Scene:
    number: int
    title: str
    run: Callable[[], None]


def _print(r: RunResult, show_findings: bool = True) -> None:
    for s in r.skipped:
        print(f"  {s}: done earlier - checkpoint verified by hash, not repeated")
    for n in r.notes:
        print(f"  {n}")
    if show_findings:
        for f in r.findings:
            mark = "x" if f.severity == "blocking" else "-"
            print(f"    [{mark}] {f.rule}: {f.detail}")
    print(f"  verdict: {r.verdict}")


def prepare(out: Path) -> None:
    if out.exists():
        for p in out.rglob("*"):
            if p.is_file():
                p.chmod(stat.S_IWRITE | stat.S_IREAD)
        shutil.rmtree(out)


def scenes(out: Path, seed: int = 20261123) -> list[Scene]:
    ws = Workspace(out)
    period = synth.PERIOD

    def s1():
        info = synth.generate(ws.sources, seed)
        planted = synth.plant_problems(ws.sources)
        print(f"  {info['members']} members, {info['studios']} studios, {info['endorsements']} endorsements, "
              f"{info['listings']} listing rows (seed {seed}); four separate CSV catalogs")
        for kind, where in planted.items():
            print(f"    planted {kind}: {where}")

    def s2():
        r = run(ws, period)
        blocking = [f for f in r.findings if f.severity == "blocking"]
        print(f"  ingest: every file hashed and counted; {r.notes[0] if r.notes else ''}")
        for n in r.notes[1:3]:
            print(f"  {n}")
        print(f"  {len(blocking)} blocking, {len(r.findings) - len(blocking)} advisory findings:")
        for f in r.findings:
            print(f"    [{'x' if f.severity == 'blocking' else '-'}] {f.rule}: {f.detail}")
        print(f"  verdict: {r.verdict} - nothing frozen, nothing printed; QA summary in qa/{period}/")

    def s3():
        for fix in synth.repair_sources(ws.sources):
            print(f"  fixed: {fix}")
        r = run(ws, period)
        print(f"  {r.notes[-1]}")
        print(f"  verdict: {r.verdict} - checks pass, but no one has signed off")

    def s4():
        try:
            run(ws, period, approve_as="directory editor", crash_after="render")
        except SimulatedCrash as exc:
            print("  freeze: snapshot frozen read-only after the directory editor approved")
            print("  render: 12 PDFs (4 districts x 3 editions) written to staging - not yet published")
            print(f"  !! {exc}")

    def s5():
        _print(run(ws, period, approve_as="directory editor", resume=True), show_findings=False)

    def s6():
        changes = synth.next_period(ws.sources)
        print(f"  December sources: {len(changes['added'])} listings added, {len(changes['withdrawn'])} withdrawn")
        _print(run(ws, "2026-12", approve_as="directory editor"), show_findings=False)

    def s7():
        ok, note = rollback(ws, "2026-11")
        print(f"  rollback to 2026-11: {'OK' if ok else 'REFUSED'} - {note}")
        print(f"  readers now get: {current(ws)}; published/ still holds 2026-11 and 2026-12")

    return [Scene(1, "Four source catalogs arrive, with problems planted", s1),
            Scene(2, "Ingest, normalise and check: the rule registry blocks the release", s2),
            Scene(3, "The directory editor fixes the sources; the checks pass", s3),
            Scene(4, "Sign-off freezes a snapshot; printing starts - and the machine stops", s4),
            Scene(5, "Resume: finished stages are skipped, every PDF is verified, then published", s5),
            Scene(6, "Next month: a new release, compared with the last one", s6),
            Scene(7, "A problem is reported: roll back to November", s7)]


def run_demo(out: Path, seed: int) -> int:
    prepare(out)
    for sc in scenes(out, seed):
        announce(sc.number, sc.title)
        sc.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "run", "rollback", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=Path("build/workspace"))
        if name == "generate":
            p.add_argument("--seed", type=int, default=20261123)
            p.add_argument("--with-problems", action="store_true")
        if name == "run":
            p.add_argument("--period", default=synth.PERIOD)
            p.add_argument("--approve", metavar="ROLE")
            p.add_argument("--resume", action="store_true")
            p.add_argument("--crash-after", choices=["check", "freeze", "render", "verify"])
        if name == "rollback":
            p.add_argument("--to", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, default=Path("build/demo"))
    demo.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo(args.out, args.seed)
    ws = Workspace(args.workspace)
    if args.command == "generate":
        print(synth.generate(ws.sources, args.seed))
        if args.with_problems:
            print(synth.plant_problems(ws.sources))
        return 0
    if args.command == "run":
        try:
            r = run(ws, args.period, approve_as=args.approve, crash_after=args.crash_after, resume=args.resume)
        except SimulatedCrash as exc:
            print(f"stopped: {exc}; rerun with --resume")
            return 3
        _print(r)
        return 0 if r.verdict == "PUBLISHED" else 1
    if args.command == "rollback":
        ok, note = rollback(ws, args.to)
        print(note)
        return 0 if ok else 1
    print(f"current: {current(ws)}")
    return 0
