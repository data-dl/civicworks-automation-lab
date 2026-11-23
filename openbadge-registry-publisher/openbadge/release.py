"""The release workflow: snapshot -> validate -> publish the data file -> verify over HTTP -> switch pointer.

The pointer (`latest.json`) is what consumers read. It moves only after the new data file has been
fetched back over HTTP and matched byte for byte, so a bad upload can never become "latest". Every
release - blocked, failed or verified - keeps its record and its evidence, and old data files are
never touched, which is what makes rollback safe.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import __version__
from .db import connect, migrate
from .registry import Finding, blocking, build_payload, canonical_bytes, validate
from .runkit import Manifest, atomic_write_bytes, atomic_write_text, sha256_bytes, sha256_file, utc_now, write_json
from .site import fetch, read_pointer, serve

PROJECT = "openbadge-registry-publisher"
INJECTIONS = ("corrupt-after-write", "missing-file")


@dataclass
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    @property
    def db(self) -> Path:
        return self.root / "registry.sqlite"

    @property
    def site(self) -> Path:
        return self.root / "site"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def tickets(self) -> Path:
        return self.root / "tickets"

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


@dataclass
class ReleaseResult:
    release_id: str
    verdict: str  # BLOCKED | DRY-RUN | VERIFY-FAILED | PUBLISHED
    record_count: int = 0
    sha256: str = ""
    findings: list[Finding] = field(default_factory=list)
    pointer: str | None = None
    notes: list[str] = field(default_factory=list)


def next_release_id(con: sqlite3.Connection) -> str:
    return f"R{con.execute('SELECT COUNT(*) FROM registry_release').fetchone()[0] + 1:04d}"


def current_payload(ws: Workspace) -> dict | None:
    pointer = read_pointer(ws.site)
    if not pointer:
        return None
    path = ws.site / pointer["path"]
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _ticket(ws: Workspace, release_id: str, kind: str, detail: str, fix: str) -> Path:
    n = len(list(ws.tickets.glob("*.md"))) + 1 if ws.tickets.exists() else 1
    path = ws.tickets / f"T{n:03d}-{release_id}-{kind}.md"
    atomic_write_text(path, f"# Correction ticket T{n:03d}\n\n- release: {release_id}\n- problem: {kind}\n"
                            f"- detail: {detail}\n- opened: {utc_now()}\n\n## What to do\n\n{fix}\n\n"
                            "_DEMO / SYNTHETIC ticket._\n")
    return path


def release(ws: Workspace, as_of: date, *, apply: bool = True, inject: str | None = None,
            accept_drop: bool = False, seed: int | None = None) -> ReleaseResult:
    if inject and inject not in INJECTIONS:
        raise ValueError(f"unknown injection {inject!r}; choose from {INJECTIONS}")
    con = ws.open()
    release_id = next_release_id(con)
    pointer = read_pointer(ws.site)
    manifest = Manifest(PROJECT, release_id, __version__, "1.0", seed, mode="apply" if apply else "dry-run",
                        previous_release_id=pointer["release_id"] if pointer else None)
    result = ReleaseResult(release_id, "DRY-RUN", pointer=pointer["release_id"] if pointer else None)
    run_dir = ws.runs / release_id

    stage = manifest.begin("snapshot")
    payload = build_payload(con, release_id, as_of)
    data = canonical_bytes(payload)
    result.record_count, result.sha256 = payload["record_count"], sha256_bytes(data)
    manifest.end(stage, records=result.record_count, sha256=result.sha256)

    stage = manifest.begin("validate")
    known = {r[0] for r in con.execute("SELECT code FROM badge_type")}
    result.findings = validate(payload, known, current_payload(ws), accept_drop=accept_drop)
    stopping = blocking(result.findings)
    manifest.end(stage, "blocked" if stopping else "ok", findings=[f.to_dict() for f in result.findings])

    def finish(verdict: str, technical_status: str | None, path: str | None = None) -> ReleaseResult:
        result.verdict = manifest.verdict = verdict
        if technical_status:
            con.execute("INSERT INTO registry_release (release_id, payload_path, sha256, record_count, "
                        "technical_status, created_at, findings_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (release_id, path, result.sha256, result.record_count, technical_status, utc_now(),
                         json.dumps([f.to_dict() for f in result.findings])))
            con.commit()
            write_json(run_dir / "findings.json", [f.to_dict() for f in result.findings])
            manifest.write(run_dir / "manifest.json")
        con.close()
        return result

    if stopping:
        result.notes.append(f"{len(stopping)} blocking finding(s); nothing published, pointer stays on "
                            f"{result.pointer or 'nothing'}")
        return finish("BLOCKED", "blocked")
    if not apply:
        result.notes.append("dry run: checks pass; rerun without --dry-run to publish")
        return finish("DRY-RUN", None)

    stage = manifest.begin("publish_data")
    relative = f"releases/registry-{release_id}.json"
    target = ws.site / relative
    if target.exists():
        manifest.end(stage, "fail")
        raise FileExistsError(f"{relative} already exists; release files are immutable")
    atomic_write_bytes(target, data)
    if inject == "corrupt-after-write":  # an upload that was cut off half way
        target.write_bytes(data[: len(data) // 2])
    elif inject == "missing-file":  # an upload that never arrived
        target.unlink()
    manifest.end(stage, path=relative, injected=inject)

    stage = manifest.begin("verify_over_http")
    problems = []
    with serve(ws.site) as base:
        status, body = fetch(f"{base}/{relative}")
    if status != 200:
        problems.append(f"GET {relative} returned HTTP {status}")
    elif sha256_bytes(body) != result.sha256:
        problems.append(f"served file hash {sha256_bytes(body)[:12]} != built {result.sha256[:12]}")
    else:
        served = json.loads(body)
        sample = [0, len(payload["badges"]) // 2, len(payload["badges"]) - 1] if payload["badges"] else []
        if served["record_count"] != result.record_count or any(
                served["badges"][i] != payload["badges"][i] for i in sample):
            problems.append("served records differ from the snapshot")
    if problems:
        manifest.end(stage, "fail", problems=problems)
        ticket = _ticket(ws, release_id, "verify-failed", "; ".join(problems),
                         "Re-run the release. The pointer was not moved, so consumers still see the previous "
                         "release; the damaged file stays in place as evidence.")
        result.notes.append(f"verification failed: {problems[0]}; pointer stays on {result.pointer}; "
                            f"ticket {ticket.name}")
        if target.exists():
            manifest.add_output(target, ws.root)
        return finish("VERIFY-FAILED", "verify-failed", relative)
    manifest.end(stage, http=status, sha256=result.sha256)
    manifest.add_output(target, ws.root)

    stage = manifest.begin("switch_pointer")
    previous = result.pointer
    con.execute("INSERT INTO registry_release (release_id, payload_path, sha256, record_count, technical_status, "
                "created_at, findings_json) VALUES (?, ?, ?, ?, 'verified', ?, ?)",
                (release_id, relative, result.sha256, result.record_count, utc_now(),
                 json.dumps([f.to_dict() for f in result.findings])))
    _switch_pointer(ws, con, release_id, relative, result.sha256, result.record_count, "new release")
    result.pointer = release_id
    manifest.end(stage, previous=previous, now=release_id)
    manifest.add_output(ws.site / "latest.json", ws.root)
    result.notes.append(f"pointer moved {previous or 'nothing'} -> {release_id}")
    result.verdict = manifest.verdict = "PUBLISHED"
    write_json(run_dir / "findings.json", [f.to_dict() for f in result.findings])
    manifest.write(run_dir / "manifest.json")
    con.close()
    return result


def _switch_pointer(ws: Workspace, con: sqlite3.Connection, release_id: str, relative: str, sha: str,
                    count: int, reason: str) -> None:
    pointer = {"release_id": release_id, "path": relative, "sha256": sha, "record_count": count,
               "schema_version": "1.0", "switched_at": utc_now(), "notice": "DEMO / SYNTHETIC"}
    write_json(ws.site / "latest.json", pointer)
    con.execute("INSERT INTO pointer_history (release_id, switched_at, reason) VALUES (?, ?, ?)",
                (release_id, pointer["switched_at"], reason))
    con.commit()


@dataclass
class ConsumerResult:
    release_id: str | None
    verdict: str  # pending | accepted | rejected
    reason: str
    ticket: str | None = None


def consume(ws: Workspace, *, delayed: bool = False) -> ConsumerResult:
    """The outside catalogue importing the registry: it trusts only what it can fetch and check."""
    con = ws.open()
    try:
        with serve(ws.site) as base:
            status, body = fetch(f"{base}/latest.json")
            if status != 200:
                return ConsumerResult(None, "rejected", f"no pointer (HTTP {status})")
            pointer = json.loads(body)
            release_id = pointer["release_id"]
            already = con.execute("SELECT COUNT(*) FROM consumer_result WHERE release_id = ?",
                                  (release_id,)).fetchone()[0]
            if delayed and not already:
                return _record(con, ws, ConsumerResult(release_id, "pending", "queued for the nightly import"))
            status, data = fetch(f"{base}/{pointer['path']}")
        if status != 200:
            return _record(con, ws, ConsumerResult(release_id, "rejected", f"missing_target: HTTP {status}"))
        if sha256_bytes(data) != pointer["sha256"]:
            return _record(con, ws, ConsumerResult(release_id, "rejected", "hash_mismatch"))
        payload = json.loads(data)
        known = {r[0] for r in con.execute("SELECT code FROM badge_type")}
        problems = blocking(validate(payload, known))
        if problems:
            return _record(con, ws, ConsumerResult(release_id, "rejected", f"schema_error: {problems[0].detail}"))
        return _record(con, ws, ConsumerResult(release_id, "accepted", f"imported {payload['record_count']} badges"))
    finally:
        con.close()


def _record(con: sqlite3.Connection, ws: Workspace, result: ConsumerResult) -> ConsumerResult:
    if result.release_id:
        con.execute("INSERT INTO consumer_result (release_id, verdict, reason, checked_at) VALUES (?, ?, ?, ?)",
                    (result.release_id, result.verdict, result.reason, utc_now()))
        con.execute("UPDATE registry_release SET consumer_status = ? WHERE release_id = ?",
                    (result.verdict, result.release_id))
        con.commit()
    if result.verdict == "rejected":
        result.ticket = _ticket(ws, result.release_id or "none", "consumer-rejected", result.reason,
                                "Check the pointer target and roll back to the last verified release if the "
                                "current one cannot be repaired: `openbadge rollback`.").name
    return result


@dataclass
class RollbackResult:
    ok: bool
    target: str | None
    reason: str


def rollback(ws: Workspace, to: str | None = None) -> RollbackResult:
    """Point consumers back at an earlier release - only one that verified, still exists, and still matches."""
    con = ws.open()
    try:
        pointer = read_pointer(ws.site)
        current = pointer["release_id"] if pointer else None
        if to is None:
            row = con.execute("SELECT release_id FROM registry_release WHERE technical_status = 'verified' "
                              "AND release_id != COALESCE(?, '') ORDER BY release_id DESC LIMIT 1",
                              (current,)).fetchone()
            if not row:
                return RollbackResult(False, None, "no earlier verified release to roll back to")
            to = row[0]
        rel = con.execute("SELECT * FROM registry_release WHERE release_id = ?", (to,)).fetchone()
        if rel is None:
            return RollbackResult(False, to, "no such release")
        if rel["technical_status"] != "verified":
            return RollbackResult(False, to, f"{to} never verified ({rel['technical_status']}); refusing")
        path = ws.site / rel["payload_path"]
        if not path.exists() or sha256_file(path) != rel["sha256"]:
            return RollbackResult(False, to, f"{to}'s data file is missing or changed; refusing")
        with serve(ws.site) as base:
            status, body = fetch(f"{base}/{rel['payload_path']}")
        if status != 200 or sha256_bytes(body) != rel["sha256"]:
            return RollbackResult(False, to, f"{to} does not verify over HTTP; refusing")
        _switch_pointer(ws, con, to, rel["payload_path"], rel["sha256"], rel["record_count"],
                        f"rollback from {current}")
        return RollbackResult(True, to, f"pointer moved {current} -> {to} (verified by hash over HTTP)")
    finally:
        con.close()


def status_rows(ws: Workspace) -> list[dict]:
    con = ws.open()
    try:
        pointer = read_pointer(ws.site)
        rows = []
        for r in con.execute("SELECT * FROM registry_release ORDER BY release_id"):
            live = pointer and pointer["release_id"] == r["release_id"]
            target_ok = r["payload_path"] and (ws.site / r["payload_path"]).exists()
            rows.append({"release": r["release_id"], "records": r["record_count"],
                         "technical": r["technical_status"], "consumer": r["consumer_status"],
                         "live": "<- latest" if live else "", "file": "present" if target_ok else "-"})
        return rows
    finally:
        con.close()
