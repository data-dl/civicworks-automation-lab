"""One day's QA run: four export jobs, each proven usable before it is trusted.

Every job does the same three things:
    1. export   produce a CSV from its source (SQL, CSV files, or the desk app's Export button)
    2. prove    the file exists AND has exactly the expected columns AND the row count the source says
                it has AND no blank keys - otherwise it is moved to quarantine/ with the reason
    3. check    only a proven export is examined for business exceptions

Then the day's outputs are published as a set: yesterday's verified set is moved into archive/ with
a SHA-256 manifest first, so it can always be restored. A quarantined job never replaces yesterday's
good file; that file is carried forward and marked stale on the dashboard.
"""

from __future__ import annotations

import csv
import html
import json
import os
import shutil
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .db import connect, migrate
from .runkit import SYNTHETIC_NOTICE, guard, replace, sha256_file, utc_now, write_json
from .sources import EXPORT_COLUMNS, CsvAdapter, DeskAppExport, SqliteAdapter

JOBS = {
    "qualification_mapping": "Every equipment class at every depot has at least one technician authorised for it",
    "attribute_completeness": "Every equipment record has a serial and a last-service date",
    "category_overlaps": "No serial number is registered under two equipment classes",
    "active_eligibility": "No technician is marked active with every authorisation lapsed",
}


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    sources = property(lambda self: self.root / "sources")
    db = property(lambda self: self.root / "ledgerguard.sqlite")
    exports = property(lambda self: self.root / "exports")
    quarantine = property(lambda self: self.root / "quarantine")
    staging = property(lambda self: self.root / "staging")
    current = property(lambda self: self.root / "current")
    archive = property(lambda self: self.root / "archive")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


@dataclass
class JobResult:
    code: str
    adapter: str
    expected: int
    observed: int
    state: str
    reason: str = ""
    exceptions: list[dict] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    file: str = ""


@dataclass
class DayResult:
    run_id: str
    jobs: list[JobResult] = field(default_factory=list)
    archived: str | None = None
    carried_forward: list[str] = field(default_factory=list)


def _write_csv(path: Path, columns: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        w.writerows(rows)
    return path


def prove(path: Path, columns: list[str], expected: int, key: str) -> tuple[bool, int, str]:
    """A file existing is not success. Returns (usable, rows observed, reason if not)."""
    if not path.exists():
        return False, 0, "no file was written"
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    if header != columns:
        missing, extra = sorted(set(columns) - set(header)), sorted(set(header) - set(columns))
        return False, len(rows), f"columns changed: missing {missing}, unexpected {extra}"
    if not guard("row-count-proof"):
        return True, len(rows), ""
    if not rows and expected:
        return False, 0, f"the file has a header but no rows; the source has {expected}"
    if len(rows) != expected:
        return False, len(rows), f"{len(rows)} rows exported, the source has {expected}"
    blank = sum(1 for r in rows if not r[key].strip())
    if blank:
        return False, len(rows), f"{blank} row(s) with a blank {key}"
    return True, len(rows), ""


def run_day(ws: Workspace, run_date: date, desk_mode: str = "normal") -> DayResult:
    con = ws.open()
    run_id = run_date.isoformat()
    con.execute("INSERT OR REPLACE INTO qa_run VALUES (?, ?, ?, 'running')", (run_id, run_id, utc_now()))
    con.execute("DELETE FROM export_job WHERE run_id = ?", (run_id,))
    day = DayResult(run_id)
    out = ws.exports / run_id
    registry = SqliteAdapter(ws.sources / "registry.sqlite")
    roster, roster_count = CsvAdapter(ws.sources / "roster.csv").rows()
    auths, _ = CsvAdapter(ws.sources / "authorizations.csv").rows()
    equipment, equipment_count = registry.equipment()
    valid = defaultdict(set)
    for a in auths:
        if date.fromisoformat(a["expiry"]) >= run_date:
            valid[a["technician_id"]].add(a["class_code"])
    depot_of = {t["technician_id"]: t["depot"] for t in roster if t["active"] == "1"}

    # 1. qualification mapping (SQL source + two CSV sources)
    pairs = sorted({(e["depot"], e["class_code"]) for e in equipment})
    cols = ["depot", "class_code", "equipment", "qualified_technicians"]
    rows = [[d, c, sum(1 for e in equipment if (e["depot"], e["class_code"]) == (d, c)),
             sum(1 for t, dep in depot_of.items() if dep == d and c in valid[t])] for d, c in pairs]
    day.jobs.append(_finish(ws, con, day, "qualification_mapping", "sqlite+csv",
                            _write_csv(out / "qualification_mapping.csv", cols, rows), cols, len(pairs), "depot",
                            lambda r: int(r["qualified_technicians"]) == 0,
                            lambda r: f"{r['equipment']} {r['class_code']} at {r['depot']} with nobody authorised"))

    # 2. attribute completeness (the desk app's export)
    path, expected, _message = DeskAppExport(ws.sources / "registry.sqlite", desk_mode).export(
        out / "attribute_completeness.csv")
    day.jobs.append(_finish(ws, con, day, "attribute_completeness", "desk-app", path, EXPORT_COLUMNS, expected,
                            "equipment_id", lambda r: not r["serial_token"] or not r["last_service"],
                            lambda r: f"{r['equipment_id']} missing "
                                      + " and ".join(x for x, v in (("serial", r["serial_token"]),
                                                                     ("last service date", r["last_service"]))
                                                     if not v)))

    # 3. category overlaps (SQL source)
    classes = defaultdict(set)
    for e in equipment:
        if e["serial_token"]:
            classes[e["serial_token"]].add(e["class_code"])
    cols = ["serial_token", "classes"]
    rows = [[s, " ".join(sorted(c))] for s, c in sorted(classes.items())]
    day.jobs.append(_finish(ws, con, day, "category_overlaps", "sqlite",
                            _write_csv(out / "category_overlaps.csv", cols, rows), cols, len(classes),
                            "serial_token", lambda r: " " in r["classes"],
                            lambda r: f"serial {r['serial_token']} is registered as {r['classes']}"))

    # 4. active eligibility (two CSV sources)
    cols = ["technician_id", "depot", "active", "valid_authorisations"]
    rows = [[t["technician_id"], t["depot"], t["active"], len(valid[t["technician_id"]])] for t in roster]
    day.jobs.append(_finish(ws, con, day, "active_eligibility", "csv",
                            _write_csv(out / "active_eligibility.csv", cols, rows), cols, roster_count,
                            "technician_id", lambda r: r["active"] == "1" and r["valid_authorisations"] == "0",
                            lambda r: f"{r['technician_id']} at {r['depot']} is active with no valid authorisation"))
    con.commit()
    _publish(ws, con, day)
    verdict = "all jobs verified" if all(j.state == "verified" for j in day.jobs) else \
        f"{sum(j.state == 'quarantined' for j in day.jobs)} job(s) quarantined"
    con.execute("UPDATE qa_run SET verdict = ? WHERE run_id = ?", (verdict, run_id))
    con.commit()
    con.close()
    return day


def _finish(ws, con, day, code, adapter, path, columns, expected, key, is_exception, describe) -> JobResult:
    ok, observed, reason = prove(path, columns, expected, key)
    result = JobResult(code, adapter, expected, observed, "verified" if ok else "quarantined", reason, columns=columns)
    if ok:
        with path.open(encoding="utf-8", newline="") as f:
            result.exceptions = [{"detail": describe(r), **r} for r in csv.DictReader(f) if is_exception(r)]
        result.file = str(path)
    else:
        target = ws.quarantine / day.run_id / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            os.replace(path, target)
        result.file = str(target)
    con.execute("INSERT INTO export_job (run_id, job_code, source_adapter, expected_rows, observed_rows, state, "
                "reason, file_sha256, exceptions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (day.run_id, code, adapter, expected, observed, result.state, reason,
                 sha256_file(result.file) if Path(result.file).exists() else "", len(result.exceptions)))
    return result


def _publish(ws: Workspace, con: sqlite3.Connection, day: DayResult) -> None:
    stage = ws.staging / day.run_id
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    previous = json.loads((ws.current / "MANIFEST.json").read_text(encoding="utf-8")) if \
        (ws.current / "MANIFEST.json").exists() else None
    for job in day.jobs:
        name = f"{job.code}.csv"
        if job.state == "verified":
            shutil.copy2(job.file, stage / name)
        elif previous and (ws.current / name).exists():
            shutil.copy2(ws.current / name, stage / name)       # yesterday's good file, kept
            day.carried_forward.append(job.code)
    status = {j.code: {"state": j.state, "expected": j.expected, "observed": j.observed, "reason": j.reason,
                       "exceptions": len(j.exceptions), "stale": j.code in day.carried_forward} for j in day.jobs}
    _workbook(stage / "exceptions.xlsx", day)
    _dashboard(stage / "dashboard.html", day, previous["run_id"] if previous else None)
    manifest = {"run_id": day.run_id, "status": status,
                "files": {p.name: sha256_file(p) for p in sorted(stage.iterdir())}}
    write_json(stage / "MANIFEST.json", manifest)
    if ws.current.exists():
        target = ws.archive / previous["run_id"] if previous else ws.archive / f"unknown-{utc_now()[:10]}"
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        replace(ws.current, target)
        for name, digest in (previous or {}).get("files", {}).items():
            # Paths relative to the workspace: the index stays valid if the workspace is moved or restored
            # elsewhere, and it never records the folder names of the machine it ran on.
            con.execute("INSERT INTO archive_item (run_id, file_name, sha256, archive_path, restore_path) "
                        "VALUES (?, ?, ?, ?, ?)", (day.run_id, name, digest, _rel(ws, target / name),
                                                   _rel(ws, ws.current / name)))
        day.archived = target.name
    replace(stage, ws.current)


def _rel(ws: Workspace, path: Path) -> str:
    return path.resolve().relative_to(ws.root.resolve()).as_posix()


def restore(ws: Workspace, run_id: str) -> tuple[bool, str]:
    """Put an archived day back as current - only if every file still matches its manifest."""
    folder = ws.archive / run_id
    if not (folder / "MANIFEST.json").exists():
        return False, f"no archived set for {run_id}"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    bad = [n for n, d in manifest["files"].items() if not (folder / n).exists() or sha256_file(folder / n) != d]
    if bad:
        return False, f"{len(bad)} archived file(s) no longer match their manifest ({bad[0]}); refusing"
    current = json.loads((ws.current / "MANIFEST.json").read_text(encoding="utf-8"))["run_id"]
    stage = ws.staging / f"restore-{run_id}"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(folder, stage)
    displaced = ws.archive / f"{current}-replaced-by-restore"
    if displaced.exists():
        shutil.rmtree(displaced)
    replace(ws.current, displaced)
    replace(stage, ws.current)
    return True, f"current is {run_id} again (all {len(manifest['files'])} files re-hashed); " \
                 f"the set it replaced is kept in archive/{displaced.name}"


def _workbook(path: Path, day: DayResult) -> None:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    summary.append([f"LedgerGuard daily QA - {day.run_id}"])
    summary["A1"].font = Font(bold=True, size=13)
    summary.append([SYNTHETIC_NOTICE])
    summary.append([])
    summary.append(["Job", "What it checks", "State", "Expected rows", "Exported rows", "Exceptions", "Reason"])
    for cell in summary[4]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F4F6F")
    for j in day.jobs:
        summary.append([j.code, JOBS[j.code], j.state, j.expected, j.observed, len(j.exceptions), j.reason])
        if j.state != "verified":
            summary.cell(row=summary.max_row, column=3).fill = PatternFill("solid", fgColor="F8CBAD")
    for col, w in zip("ABCDEFG", (24, 60, 12, 13, 13, 11, 50), strict=True):
        summary.column_dimensions[col].width = w
    for j in day.jobs:
        sheet = wb.create_sheet(j.code[:31])
        sheet.append(["Exception"] + j.columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for e in j.exceptions:
            sheet.append([e["detail"]] + [e.get(c, "") for c in j.columns])
        if j.state != "verified":
            sheet.append([f"QUARANTINED - not checked: {j.reason}"])
        sheet.column_dimensions["A"].width = 60
    wb.properties.creator = "CivicWorks demo"
    wb.save(path)


def _dashboard(path: Path, day: DayResult, previous: str | None) -> None:
    cards, details = [], []
    for j in day.jobs:
        stale = j.code in day.carried_forward
        state = "quarantined" + (" (yesterday's file kept)" if stale else "") if j.state != "verified" else "verified"
        cards.append(f"<div class='card {j.state}'><h3>{j.code.replace('_', ' ')}</h3><p class='what'>"
                     f"{html.escape(JOBS[j.code])}</p><p class='state'>{state}</p><p>{j.observed} of {j.expected} "
                     f"rows | {len(j.exceptions)} exceptions</p>"
                     + (f"<p class='reason'>{html.escape(j.reason)}</p>" if j.reason else "") + "</div>")
        rows = "".join(f"<li>{html.escape(e['detail'])}</li>" for e in j.exceptions) or "<li>none</li>"
        details.append(f"<details><summary>{j.code} - {len(j.exceptions)} exceptions</summary>"
                       f"<ul>{rows}</ul></details>")
    path.write_text(f"""<!doctype html><meta charset="utf-8"><title>LedgerGuard {day.run_id}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;background:#f4f6f8;color:#1d2733;margin:0;padding:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}
.card{{background:#fff;border:1px solid #d9e0e7;border-left:5px solid #2f6f8f;border-radius:6px;padding:12px}}
.card.quarantined{{border-left-color:#a8322d}} .state{{font-weight:600}} .quarantined .state{{color:#a8322d}}
.what,.reason{{color:#5a6878;font-size:13px}} details{{background:#fff;border:1px solid #d9e0e7;border-radius:6px;
padding:8px 12px;margin-top:8px}}</style>
<h1>LedgerGuard daily QA - {day.run_id}</h1><p>{html.escape(SYNTHETIC_NOTICE)} Previous verified set:
{previous or 'none'}.</p><div class="grid">{''.join(cards)}</div><h2>Exceptions</h2>{''.join(details)}""",
                    encoding="utf-8")
