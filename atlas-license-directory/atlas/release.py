"""The release run: check -> freeze -> render -> verify -> publish, with a checkpoint after each stage.

A crash between stages loses nothing: `run(..., resume=True)` reads the checkpoint file, re-checks the
hash of what each finished stage produced, and carries on from the first stage that is not provably
done. Publishing moves a fully verified folder into place in one rename; the previous period's
directory is never touched, and `CURRENT.json` says which one readers get. Rollback points
CURRENT back at an earlier period only after re-hashing every file in it.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .pdf import EDITIONS, read_entries, render, verify
from .runkit import Manifest, sha256_bytes, sha256_file, utc_now, write_json
from .stages import Workspace, freeze, ingest_and_check
from .synth import DISTRICTS

STAGES = ["check", "freeze", "render", "verify", "publish"]


class SimulatedCrash(Exception):
    """Stands in for the machine stopping between two stages."""


@dataclass
class RunResult:
    period: str
    stopped_at: str | None = None
    verdict: str = ""
    notes: list[str] = field(default_factory=list)
    findings: list = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _state_path(ws: Workspace, period: str) -> Path:
    return ws.runs / period / "state.json"


def _load_state(ws: Workspace, period: str) -> dict:
    path = _state_path(ws, period)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"done": {}}


def _save_state(ws: Workspace, period: str, state: dict) -> None:
    write_json(_state_path(ws, period), state)


def _folder_hash(folder: Path) -> str:
    return sha256_bytes("\n".join(f"{p.name}={sha256_file(p)}" for p in sorted(folder.glob("*.pdf"))).encode())


def _stage_proof(ws: Workspace, period: str, stage: str) -> str | None:
    """Something that proves a stage's output is still intact; None if it is not."""
    if stage == "check":
        path = ws.qa / period / "qa_summary.json"
        return sha256_file(path) if path.exists() else None
    if stage == "freeze":
        path = ws.snapshots / period / "snapshot.sqlite"
        return sha256_file(path) if path.exists() else None
    if stage in ("render", "verify"):
        folder = ws.staging / period
        if not folder.exists() and (ws.published / period).exists():
            folder = ws.published / period   # already moved into place by publish
        return _folder_hash(folder) if folder.exists() and any(folder.glob("*.pdf")) else None
    folder = ws.published / period
    return _folder_hash(folder) if folder.exists() else None


def run(ws: Workspace, period: str, *, approve_as: str | None = None, crash_after: str | None = None,
        resume: bool = False, seed: int | None = None) -> RunResult:
    result = RunResult(period)
    state = _load_state(ws, period) if resume else {"done": {}}
    manifest = Manifest("atlas-license-directory", f"{period}-{utc_now()[11:19].replace(':', '')}", __version__,
                        "1", seed, mode="publish" if approve_as else "review")
    for stage in STAGES:
        proof = state["done"].get(stage)
        if proof and proof == _stage_proof(ws, period, stage):
            result.skipped.append(stage)
            continue
        record = manifest.begin(stage)
        ok, note = _run_stage(ws, period, stage, approve_as, result)
        manifest.end(record, "ok" if ok else "blocked", note=note)
        result.notes.append(f"{stage}: {note}")
        if not ok:
            result.stopped_at = stage
            result.verdict = f"STOPPED at {stage}"
            break
        state["done"][stage] = _stage_proof(ws, period, stage)
        _save_state(ws, period, state)
        if crash_after == stage:
            manifest.verdict = f"interrupted after {stage}"
            manifest.write(ws.runs / period / f"manifest-{manifest.run_id}.json")
            raise SimulatedCrash(f"process stopped after {stage}")
    else:
        result.verdict = "PUBLISHED"
    manifest.verdict = result.verdict
    manifest.write(ws.runs / period / f"manifest-{manifest.run_id}.json")
    return result


def _set_release(ws: Workspace, period: str, **fields) -> None:
    con = ws.open()
    sets = ", ".join(f"{k} = ?" for k in fields)
    con.execute(f"UPDATE directory_release SET {sets}, updated_at = ? WHERE release_id = ?",  # noqa: S608
                (*fields.values(), utc_now(), period))
    con.commit()
    con.close()


def _run_stage(ws: Workspace, period: str, stage: str, approve_as: str | None, result: RunResult) -> tuple[bool, str]:
    if stage == "check":
        checked = ingest_and_check(ws, period)
        result.findings = checked.findings
        result.notes.extend(checked.notes)
        if checked.blocking:
            return False, f"{len(checked.blocking)} blocking finding(s); see qa/{period}/qa_summary.html"
        return True, f"no blocking findings ({len(checked.findings)} advisory)"
    if stage == "freeze":
        if (ws.snapshots / period / "snapshot.sqlite").exists():
            return True, "already frozen"
        return freeze(ws, period, approve_as)
    snapshot = ws.snapshots / period / "snapshot.sqlite"
    if stage == "render":
        folder = ws.staging / period
        if folder.exists():
            shutil.rmtree(folder)
        count = 0
        for code, _ in DISTRICTS:
            for edition in EDITIONS:
                render(snapshot, code, edition, period, folder / f"{code}-{edition}.pdf")
                count += 1
        _set_release(ws, period, stage="rendered", pdf_count=count)
        return True, f"{count} PDFs rendered into staging/{period}/ (not yet published)"
    if stage == "verify":
        from .pdf import plan

        problems = []
        for code, _ in DISTRICTS:
            for edition in EDITIONS:
                p = plan(code, edition, read_entries(snapshot, code, edition))
                problems += [f"{code}-{edition}: {x}" for x in verify(ws.staging / period / f"{code}-{edition}.pdf", p)]
        if problems:
            return False, f"{len(problems)} problem(s), e.g. {problems[0]}"
        _set_release(ws, period, stage="verified")
        return True, "all 12 PDFs verified: page counts, contents links, index last and linked, bookmarks, footers"
    # publish
    target = ws.published / period
    if target.exists():
        return True, "already published"
    staged = ws.staging / period
    manifest = {p.name: sha256_file(p) for p in sorted(staged.glob("*.pdf"))}
    write_json(staged / "MANIFEST.json", manifest)
    ws.published.mkdir(parents=True, exist_ok=True)
    os.replace(staged, target)  # one rename: readers see all twelve files or none
    previous = current(ws)
    write_json(ws.published / "CURRENT.json", {"period": period, "switched_at": utc_now(), "reason": "new release",
                                              "manifest_sha256": sha256_file(target / "MANIFEST.json")})
    _set_release(ws, period, stage="published", manifest_hash=sha256_file(target / "MANIFEST.json"))
    delta = delta_report(ws, previous, period) if previous else "first release"
    return True, f"published/{period}/ is now current; previous: {previous or 'none'}; changes: {delta}"


def current(ws: Workspace) -> str | None:
    path = ws.published / "CURRENT.json"
    return json.loads(path.read_text(encoding="utf-8"))["period"] if path.exists() else None


def _listing_keys(snapshot: Path) -> set[tuple]:
    con = sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True)
    keys = set(con.execute("SELECT member_id, studio_id, edition_code FROM placement WHERE approved = 1"))
    con.close()
    return keys


def delta_report(ws: Workspace, before: str, after: str) -> str:
    old = _listing_keys(ws.snapshots / before / "snapshot.sqlite")
    new = _listing_keys(ws.snapshots / after / "snapshot.sqlite")
    added, removed = sorted(new - old), sorted(old - new)
    lines = [f"# Directory changes {before} -> {after}", "", "_DEMO / SYNTHETIC_", "",
             f"- listings added: {len(added)}", f"- listings withdrawn: {len(removed)}", ""]
    lines += [f"- added: {m} at {s} ({e})" for m, s, e in added] + [f"- withdrawn: {m} at {s} ({e})"
                                                                    for m, s, e in removed]
    (ws.published / after / "CHANGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"{len(added)} added, {len(removed)} withdrawn (CHANGES.md)"


def rollback(ws: Workspace, to: str) -> tuple[bool, str]:
    folder = ws.published / to
    manifest_path = folder / "MANIFEST.json"
    if not manifest_path.exists():
        return False, f"{to} was never published"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    damaged = [name for name, digest in manifest.items()
               if not (folder / name).exists() or sha256_file(folder / name) != digest]
    if damaged:
        return False, f"{len(damaged)} file(s) in {to} no longer match their manifest; refusing"
    was = current(ws)
    write_json(ws.published / "CURRENT.json", {"period": to, "manifest_sha256": sha256_file(manifest_path),
                                              "switched_at": utc_now(), "reason": f"rollback from {was}"})
    if was:
        _set_release(ws, was, stage="rolled-back")
    return True, f"CURRENT now points at {to} (all {len(manifest)} files re-hashed); {was} kept, not deleted"
