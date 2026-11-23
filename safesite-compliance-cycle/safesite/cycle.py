"""The quarterly cycle: plan assignments, then - as of any date - take in returns, check them, and draft
the reminders that date calls for.

Reminder rules (all drafts; nothing is sent):
    T-14        14 days before the due date, to every coordinator whose return is still open
    T-3         3 days before, the same
    overdue     after the due date, to the coordinator with the safety lead copied
    correction  as soon as a return fails its checks, saying exactly what to fix
Each (assignment, kind) gets at most one draft, so running the cycle twice on the same day changes
nothing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

from .db import connect, migrate
from .runkit import Outbox, sha256_file

SEVERITIES = ("S1", "S2", "S3", "S4")
ACTIONS = ("open", "in-progress", "closed")
COLUMNS = ["Observation ID", "Date", "Area", "Severity", "Description", "Action", "Evidence ref"]
SAFETY_LEAD = "safety.lead@example.org"


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    db = property(lambda self: self.root / "safesite.sqlite")
    submissions = property(lambda self: self.root / "submissions")
    outbox = property(lambda self: self.root / "outbox")
    working = property(lambda self: self.root / "working")
    qa = property(lambda self: self.root / "qa")
    final = property(lambda self: self.root / "final")
    runs = property(lambda self: self.root / "runs")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


@dataclass
class CheckResult:
    ok: bool
    problems: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)


def check_return(path: Path, quarter_start: date, quarter_end: date) -> CheckResult:
    """Everything a coordinator's spreadsheet must satisfy before its numbers are used."""
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any unreadable file is a problem to report, not a crash
        return CheckResult(False, [f"cannot open the file ({exc.__class__.__name__})"])
    if "Observations" not in wb.sheetnames or "Totals" not in wb.sheetnames:
        return CheckResult(False, ["needs both an Observations and a Totals sheet"])
    rows = list(wb["Observations"].iter_rows(values_only=True))
    if not rows or list(rows[0]) != COLUMNS:
        return CheckResult(False, [f"Observations columns must be exactly: {', '.join(COLUMNS)}"])
    result = CheckResult(True)
    seen = set()
    for n, raw in enumerate(rows[1:], start=2):
        rec = dict(zip(COLUMNS, raw, strict=False))
        oid = rec["Observation ID"]
        if oid in seen:
            result.problems.append(f"row {n}: observation {oid} appears twice")
        seen.add(oid)
        if rec["Severity"] not in SEVERITIES:
            result.problems.append(f"row {n}: severity '{rec['Severity']}' is not one of {', '.join(SEVERITIES)}")
        if rec["Action"] not in ACTIONS:
            result.problems.append(f"row {n}: action '{rec['Action']}' is not one of {', '.join(ACTIONS)}")
        try:
            observed = date.fromisoformat(str(rec["Date"]))
            if not quarter_start <= observed <= quarter_end:
                result.problems.append(f"row {n}: {observed} is outside the quarter")
        except ValueError:
            result.problems.append(f"row {n}: '{rec['Date']}' is not a date")
        if rec["Severity"] in ("S3", "S4") and not rec["Evidence ref"]:
            result.problems.append(f"row {n}: {oid} is {rec['Severity']} but has no evidence reference")
        result.rows.append(rec)
    declared = {str(r[0]): r[1] for r in list(wb["Totals"].iter_rows(values_only=True))[1:] if r and r[0]}
    for sev in SEVERITIES:
        counted = sum(1 for r in result.rows if r["Severity"] == sev)
        if declared.get(sev, 0) != counted:
            result.problems.append(f"Totals says {declared.get(sev, 0)} {sev} but the sheet lists {counted}")
    wb.close()
    result.ok = not result.problems
    return result


def quarter_bounds(quarter: str) -> tuple[date, date]:
    year, q = int(quarter[:4]), int(quarter[-1])
    start = date(year, 3 * q - 2, 1)
    end = date(year + (q == 4), 1 if q == 4 else 3 * q + 1, 1) - timedelta(days=1)
    return start, end


def plan_quarter(con: sqlite3.Connection, quarter: str, due: date) -> list[sqlite3.Row]:
    """One assignment per facility: depots go to the depots coordinator, workshops to their district's."""
    by_district = {"HW": "C1", "MD": "C2", "RQ": "C3"}
    for f in con.execute("SELECT * FROM facility ORDER BY facility_id").fetchall():
        coordinator = "C4" if f["category"] == "depot" else by_district[f["area_code"]]
        con.execute("INSERT OR IGNORE INTO assignment (assignment_id, quarter, facility_id, coordinator_id, due_at) "
                    "VALUES (?, ?, ?, ?, ?)", (f"{quarter}-{f['facility_id']}", quarter, f["facility_id"],
                                               coordinator, due.isoformat()))
    con.commit()
    return con.execute("SELECT a.*, f.name, c.role, c.fictional_email FROM assignment a JOIN facility f "
                       "USING (facility_id) JOIN coordinator c USING (coordinator_id) WHERE quarter = ? "
                       "ORDER BY assignment_id", (quarter,)).fetchall()


@dataclass
class CycleReport:
    as_of: date
    received: list[str] = field(default_factory=list)
    accepted: list[str] = field(default_factory=list)
    corrections: list[tuple[str, list[str]]] = field(default_factory=list)
    reminders: list[tuple[str, str]] = field(default_factory=list)
    states: dict[str, int] = field(default_factory=dict)


def _latest_return(folder: Path, facility_id: str) -> Path | None:
    files = sorted(folder.glob(f"{facility_id}_v*.xlsx"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    return files[-1] if files else None


def _arrival(path: Path) -> date:
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def run_cycle(ws: Workspace, quarter: str, as_of: date, arrivals: dict[str, date] | None = None) -> CycleReport:
    """`arrivals` maps file name -> the day it arrived (the demo knows; otherwise the file time is used)."""
    con = ws.open()
    report = CycleReport(as_of)
    start, end = quarter_bounds(quarter)
    outbox = Outbox(ws.outbox / quarter)
    folder = ws.submissions / quarter
    rows = con.execute("SELECT a.*, f.name, c.role, c.fictional_email FROM assignment a JOIN facility f "
                       "USING (facility_id) JOIN coordinator c USING (coordinator_id) WHERE quarter = ? "
                       "ORDER BY assignment_id", (quarter,)).fetchall()
    if not rows:
        raise ValueError(f"no assignments for {quarter}; run `safesite plan` first")

    for a in rows:
        aid, due = a["assignment_id"], date.fromisoformat(a["due_at"])
        latest = _latest_return(folder, a["facility_id"]) if folder.exists() else None
        if latest and latest.name != a["file_name"]:
            arrived = (arrivals or {}).get(latest.name) or _arrival(latest)
            report.received.append(latest.name)
            check = check_return(latest, start, end)
            con.execute("DELETE FROM observation WHERE assignment_id = ?", (aid,))
            if check.ok:
                state = "accepted" if arrived <= due else "accepted-late"
                con.executemany("INSERT INTO observation VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                [(r["Observation ID"], aid, str(r["Date"]), r["Area"], r["Severity"],
                                  r["Description"], r["Action"], r["Evidence ref"] or "") for r in check.rows])
                report.accepted.append(f"{a['facility_id']} ({'late' if state == 'accepted-late' else 'on time'})")
                note = ""
            else:
                state, note = "correction-requested", "; ".join(check.problems)
                report.corrections.append((a["facility_id"], check.problems))
                con.execute("DELETE FROM reminder WHERE assignment_id = ? AND kind = 'correction'", (aid,))
                path = outbox.draft(f"{aid}-correction-{latest.stem}", [a["fictional_email"]],
                                    f"Please correct your {quarter} safety return for {a['name']}",
                                    f"Hello {a['role']},\n\nYour return {latest.name} could not be accepted:\n"
                                    + "\n".join(f"  - {p}" for p in check.problems)
                                    + f"\n\nPlease send a corrected version by {due.isoformat()}.\n")
                con.execute("INSERT INTO reminder (assignment_id, kind, as_of, draft_path) VALUES (?, 'correction', "
                            "?, ?)", (aid, as_of.isoformat(), path.name))
                report.reminders.append((a["facility_id"], "correction"))
            con.execute("UPDATE assignment SET state = ?, submitted_on = ?, file_name = ?, file_sha256 = ?, note = ? "
                        "WHERE assignment_id = ?", (state, arrived.isoformat(), latest.name, sha256_file(latest),
                                                    note, aid))
        state = con.execute("SELECT state FROM assignment WHERE assignment_id = ?", (aid,)).fetchone()[0]
        if state in ("open", "overdue"):
            kind = ("overdue" if as_of > due else "T-3" if as_of >= due - timedelta(days=3)
                    else "T-14" if as_of >= due - timedelta(days=14) else None)
            if kind == "overdue" and state == "open":
                con.execute("UPDATE assignment SET state = 'overdue' WHERE assignment_id = ?", (aid,))
            if kind and not con.execute("SELECT 1 FROM reminder WHERE assignment_id = ? AND kind = ?",
                                        (aid, kind)).fetchone():
                to = [a["fictional_email"]] + ([SAFETY_LEAD] if kind == "overdue" else [])
                days = (due - as_of).days
                when = f"in {days} days" if days > 0 else f"{-days} days ago"
                path = outbox.draft(f"{aid}-{kind}", to, f"{quarter} safety return for {a['name']} - due {when}",
                                    f"Hello {a['role']},\n\nThe {quarter} safety observations return for "
                                    f"{a['name']} is due {due.isoformat()} ({when}).\n"
                                    "Use the Observations and Totals sheets of the template.\n")
                con.execute("INSERT INTO reminder (assignment_id, kind, as_of, draft_path) VALUES (?, ?, ?, ?)",
                            (aid, kind, as_of.isoformat(), path.name))
                report.reminders.append((a["facility_id"], kind))
    con.commit()
    for state, count in con.execute("SELECT state, COUNT(*) FROM assignment WHERE quarter = ? GROUP BY state",
                                    (quarter,)):
        report.states[state] = count
    con.close()
    return report
