"""Apply: write only approved decisions into the master workbook, reversibly.

    1. read the decisions file and validate every line against its proposal
    2. drop decisions already recorded (same decision hash) - applying twice changes nothing
    3. dry run by default: show exactly which cells would change
    4. with --apply: back up the master and verify the copy's hash
    5. change only the decided cells, stamp "Last changed", add a new dated Changes tab
    6. reopen the result and prove every other cell of every existing sheet is untouched -
       including the reference rows far below the data; if not, restore the backup
    7. swap the new file in atomically and record each write with the workbook's new hash
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from openpyxl import load_workbook
from openpyxl.styles import Font

from .runkit import sha256_file, utc_now
from .steward import PRECEDENCE, Workspace
from .synth import MASTER_COLUMNS


@dataclass
class ApplyResult:
    mode: str
    planned: list[dict] = field(default_factory=list)
    already_applied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    sheet: str = ""
    backup: str = ""
    preserved_cells: int = 0
    master_sha256: str = ""


def _decision_hash(row: dict) -> str:
    text = "|".join(row.get(k, "").strip() for k in ("proposal_id", "resolution", "value"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot(path: Path) -> dict[str, dict[tuple[int, int], object]]:
    wb = load_workbook(path)
    snap = {ws.title: {(c.row, c.column): c.value for row in ws.iter_rows() for c in row if c.value is not None}
            for ws in wb.worksheets}
    wb.close()
    return snap


def apply_decisions(ws: Workspace, decisions_file: Path, *, apply: bool = False,
                    today: date | None = None) -> ApplyResult:
    today = today or date.today()
    allowed = {k: v["allowed"] for k, v in yaml.safe_load(PRECEDENCE.read_text(encoding="utf-8"))["fields"].items()}
    con = ws.open()
    result = ApplyResult("apply" if apply else "dry-run")
    with decisions_file.open(encoding="utf-8", newline="") as f:
        lines = list(csv.DictReader(f))
    accepted = []
    for n, line in enumerate(lines, start=2):
        pid, resolution = line["proposal_id"].strip(), line["resolution"].strip().lower()
        if not resolution:
            result.skipped.append(pid)
            continue
        proposal = con.execute("SELECT * FROM proposal WHERE proposal_id = ?", (pid,)).fetchone()
        if proposal is None:
            result.errors.append(f"line {n}: no proposal {pid}")
            continue
        if not line["approver_role"].strip() or not line["rationale"].strip():
            result.errors.append(f"line {n}: {pid} needs an approver role and a rationale")
            continue
        value = line["value"].strip()
        if resolution not in ("approve", "reject", "choose"):
            result.errors.append(f"line {n}: resolution must be approve, reject or choose")
            continue
        if proposal["kind"] == "hold" and resolution == "approve":
            result.errors.append(f"line {n}: {pid} is a hold - choose a value or reject")
            continue
        if resolution == "approve" and value != proposal["proposed"]:
            result.errors.append(f"line {n}: approving {pid} must keep the proposed value {proposal['proposed']!r}")
            continue
        if resolution == "choose" and value not in allowed.get(proposal["field_code"], []):
            result.errors.append(f"line {n}: {value!r} is not allowed for {proposal['field_code']}")
            continue
        digest = _decision_hash(line)
        if con.execute("SELECT 1 FROM stewardship_decision WHERE decision_hash = ?", (digest,)).fetchone():
            result.already_applied.append(pid)
            continue
        accepted.append((proposal, resolution, value, line, digest))
        if resolution != "reject":
            result.planned.append({"proposal": pid, "entity": proposal["entity_id"], "field": proposal["field_code"],
                                   "old": proposal["current_value"], "new": value})
    if result.errors or not apply or not accepted:
        con.close()
        return result

    # 4. backup, verified
    ws.backups.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "").replace("-", "")[:15]
    backup = ws.backups / f"{ws.master.stem}_{stamp}{ws.master.suffix}"
    shutil.copy2(ws.master, backup)
    if sha256_file(backup) != sha256_file(ws.master):
        raise OSError("backup copy does not match the master; nothing changed")
    result.backup = backup.name
    before = _snapshot(ws.master)

    # 5. write the decided cells and a new Changes tab
    wb = load_workbook(ws.master)
    master = wb["Master"]
    row_of = {master.cell(row=r, column=1).value: r for r in range(2, 200) if master.cell(row=r, column=1).value}
    col_of = {name: i for i, name in enumerate(MASTER_COLUMNS, start=1)}
    sheet = f"Changes {today.isoformat()}"
    n = 2
    while sheet in wb.sheetnames:
        sheet = f"Changes {today.isoformat()} ({n})"
        n += 1
    log = wb.create_sheet(sheet)
    log.append(["Entity ID", "Field", "Old", "New", "Decision", "Approver role", "Rationale"])
    for cell in log[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCDEFG", (11, 22, 16, 16, 32, 17, 48), strict=True):
        log.column_dimensions[col].width = width
    touched = set()
    for proposal, resolution, value, line, _ in accepted:
        if resolution == "reject":
            continue
        r, c = row_of[proposal["entity_id"]], col_of[proposal["field_code"]]
        master.cell(row=r, column=c, value=value)
        master.cell(row=r, column=col_of["Last changed"], value=today.isoformat())
        touched |= {(r, c), (r, col_of["Last changed"])}
        log.append([proposal["entity_id"], proposal["field_code"], proposal["current_value"], value,
                    proposal["proposal_id"], line["approver_role"], line["rationale"]])
    result.sheet = sheet
    temp = ws.master.with_name(f".writing-{ws.master.name}")
    wb.save(temp)
    wb.close()

    # 6. prove nothing else moved
    after = _snapshot(temp)
    problems = [name for name in before if name not in after]
    for name, cells in before.items():
        for key, value in cells.items():
            if (name, key) in {("Master", t) for t in touched}:
                continue
            if after.get(name, {}).get(key) != value:
                problems.append(f"{name}!{key}")
        result.preserved_cells += len(cells)
    if problems:
        temp.unlink()
        raise RuntimeError(f"write-back would disturb {problems[:5]}; master left as it was")

    # 7. swap in and record
    os.replace(temp, ws.master)
    result.master_sha256 = sha256_file(ws.master)
    for proposal, resolution, value, line, digest in accepted:
        cur = con.execute("INSERT INTO stewardship_decision (proposal_id, resolution, value, approver_role, rationale, "
                          "decided_at, decision_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (proposal["proposal_id"], resolution, value, line["approver_role"], line["rationale"],
                           utc_now(), digest))
        if resolution != "reject":
            con.execute("INSERT INTO history_write (decision_id, sheet_name, backup_name, snapshot_hash, written_at) "
                        "VALUES (?, ?, ?, ?, ?)", (cur.lastrowid, sheet, backup.name, result.master_sha256, utc_now()))
    con.commit()
    con.close()
    return result
