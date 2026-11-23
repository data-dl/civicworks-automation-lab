"""Propose: turn three feeds into field-level assertions, resolve each field by the precedence matrix,
and write a review queue. Nothing in the master changes here.

Every field of every entity ends in exactly one of:
    no change     the sources agree with the master
    change        a value to write, with the source that justifies it
    hold          the sources disagree (and no authority settles it), the value is not in the vocabulary,
                  or a required value is missing - a person decides; the system never guesses
    exclude       the entity is out of scope (e.g. a retail showroom), recorded with the reason
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .db import connect, migrate
from .synth import FIELDS, MASTER_COLUMNS

PRECEDENCE = Path(__file__).with_name("precedence.yaml")


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    db = property(lambda self: self.root / "steward.sqlite")
    feeds = property(lambda self: self.root / "feeds")
    master = property(lambda self: self.root / "master" / "Guild_Workshop_Master.xlsx")
    backups = property(lambda self: self.root / "master" / "backups")
    review = property(lambda self: self.root / "review")
    runs = property(lambda self: self.root / "runs")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


def load_rules(path: Path = PRECEDENCE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_master(path: Path) -> dict[str, dict]:
    wb = load_workbook(path, read_only=True)
    rows = list(wb["Master"].iter_rows(min_row=1, max_row=200, values_only=True))
    wb.close()
    header = list(rows[0])
    out = {}
    for row in rows[1:]:
        if row and isinstance(row[0], str) and row[0].startswith("GJF-"):
            out[row[0]] = {k: ("" if v is None else str(v)) for k, v in zip(header, row, strict=False)}
    return out


@dataclass
class ProposeResult:
    cycle: str
    changes: list[dict] = field(default_factory=list)
    holds: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    duplicates_ignored: int = 0
    agreed: int = 0
    review_file: str = ""


def load_assertions(con: sqlite3.Connection, ws: Workspace, cycle: str) -> int:
    """Every non-empty field value from every feed row; identical repeats are ignored by the UNIQUE key."""
    con.execute("DELETE FROM source_assertion WHERE cycle = ?", (cycle,))
    ignored = 0
    for source in ("registry", "contract", "site"):
        with (ws.feeds / cycle / f"{source}.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                eid = row["entity_id"]
                con.execute("INSERT OR IGNORE INTO workshop_entity VALUES (?, ?)",
                            (eid, row.get("workshop_name") or eid))
                for key, value in row.items():
                    if key in ("entity_id", "workshop_name", "observed_at") or not value:
                        continue
                    cur = con.execute("INSERT OR IGNORE INTO source_assertion (cycle, entity_id, field_code, "
                                      "asserted_value, source_code, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
                                      (cycle, eid, key, value, source, row["observed_at"]))
                    ignored += cur.rowcount == 0
    con.commit()
    return ignored


def resolve(values: dict[str, set[str]], spec: dict, current: str, fallback: str | None) -> tuple[str, str, str]:
    """-> (kind, value, explanation). kind: same | change | hold."""
    order = spec["order"]
    present = {s: values[s] for s in order if values.get(s)}
    authority = spec.get("authority")
    if authority in present:
        if len(present[authority]) > 1:
            return "hold", "", f"{authority} itself gives {sorted(present[authority])}"
        value = next(iter(present[authority]))
        others = {s: v for s, v in present.items() if s != authority and v != {value}}
        why = f"{authority} (authority) says {value}"
        if others:
            why += "; " + ", ".join(f"{s} says {'/'.join(sorted(v))}" for s, v in others.items()) + " - not used"
    elif present:
        distinct = set().union(*present.values())
        if len(distinct) > 1:
            return "hold", "", "sources disagree: " + ", ".join(f"{s} says {'/'.join(sorted(v))}"
                                                                for s, v in present.items())
        value = distinct.pop()
        why = " and ".join(present) + (" say " if len(present) > 1 else " says ") + value
    elif fallback and not current:
        value, why = fallback, f"no source gives one; filled from the postcode fallback map ({fallback})"
    elif spec.get("required") and not current:
        return "hold", "", "UNKNOWN: no source gives a value and the master has none (missing, not ineligible)"
    else:
        return "same", current, "no source asserts it; master value kept"
    if value not in spec["allowed"]:
        return "hold", "", f"'{value}' is not in the allowed list {spec['allowed']}"
    return ("same" if value == current else "change"), value, why


def propose(ws: Workspace, cycle: str) -> ProposeResult:
    rules = load_rules()
    con = ws.open()
    result = ProposeResult(cycle)
    result.duplicates_ignored = load_assertions(con, ws, cycle)
    master = read_master(ws.master)
    con.execute("DELETE FROM proposal WHERE proposal_id NOT IN (SELECT proposal_id FROM stewardship_decision)")
    asserted: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    postcode: dict[str, str] = {}
    for a in con.execute("SELECT * FROM source_assertion WHERE cycle = ?", (cycle,)):
        if a["field_code"] == "postcode_token":
            postcode[a["entity_id"]] = a["asserted_value"]
        else:
            asserted[a["entity_id"]][a["field_code"]][a["source_code"]].add(a["asserted_value"])

    decided = {r["proposal_id"]: r["value"] for r in con.execute(
        "SELECT d.proposal_id, d.value FROM stewardship_decision d WHERE d.resolution IN ('approve', 'choose')")}

    def add(kind: str, eid: str, fld: str, current: str, proposed: str, why: str, evidence: dict) -> dict:
        # stable ids: the same question about the same field always has the same id
        pid = {"change": "P", "hold": "H", "exclude": "X"}[kind] + f"-{eid}-{fld}"
        row = {"proposal_id": pid, "entity_id": eid, "workshop": master.get(eid, {}).get("Workshop", eid),
               "field": fld, "current": current, "proposed": proposed, "explanation": why}
        if pid not in decided:
            con.execute("INSERT INTO proposal VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(proposal_id) DO UPDATE "
                        "SET cycle = excluded.cycle, current_value = excluded.current_value, "
                        "proposed = excluded.proposed, explanation = excluded.explanation, "
                        "evidence_json = excluded.evidence_json",
                        (pid, cycle, eid, fld, current, proposed, kind, why,
                         json.dumps({s: sorted(v) for s, v in evidence.items()})))
        return row

    def settled(eid: str, fld: str, current: str) -> bool:
        """A hold a person already decided, whose decision is what the master now holds."""
        return decided.get(f"H-{eid}-{fld}") == current and current != ""

    for eid in sorted(master):
        record = master[eid]
        if record.get("Scope") == "excluded":
            continue
        type_values = asserted[eid]["workshop_type"]
        out_of_scope = set(rules["out_of_scope"]["workshop_type"])
        if type_values.get("registry", set()) & out_of_scope:
            result.excluded.append(add("exclude", eid, "Scope", record["Scope"], "excluded",
                                       f"registry classifies it as {sorted(type_values['registry'])[0]}, which is "
                                       "out of scope for the master", type_values))
            continue
        for fld in FIELDS:
            spec = rules["fields"][fld]
            fallback = rules["geozone"].get(postcode.get(eid, "")) if spec.get("fallback") == "geozone" else None
            kind, value, why = resolve(asserted[eid][fld], spec, record.get(fld, ""), fallback)
            if kind == "same" or (kind == "hold" and settled(eid, fld, record.get(fld, ""))):
                result.agreed += 1
            elif kind == "change":
                result.changes.append(add("change", eid, fld, record.get(fld, ""), value, why, asserted[eid][fld]))
            else:
                result.holds.append(add("hold", eid, fld, record.get(fld, ""), "", why, asserted[eid][fld]))
    con.commit()
    con.close()
    result.review_file = str(write_review_queue(ws, result))
    return result


def write_review_queue(ws: Workspace, r: ProposeResult) -> Path:
    path = ws.review / f"Review_queue_{r.cycle}.xlsx"
    wb = Workbook()
    head = (Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="5B3A29"))
    for title, rows, fill in (("Holds - decide", r.holds, "F8CBAD"), ("Changes - approve", r.changes, "E2F0D9"),
                              ("Exclusions", r.excluded, "EDEDED")):
        ws_ = wb.create_sheet(title)
        ws_.append(["Proposal", "Entity", "Workshop", "Field", "Master now", "Proposed", "Why"])
        for cell in ws_[1]:
            cell.font, cell.fill = head
        for row in rows:
            ws_.append([row["proposal_id"], row["entity_id"], row["workshop"], row["field"], row["current"],
                        row["proposed"], row["explanation"]])
            for cell in ws_[ws_.max_row]:
                cell.fill = PatternFill("solid", fgColor=fill)
        for col, width in zip("ABCDEFG", (16, 10, 22, 20, 14, 14, 90), strict=True):
            ws_.column_dimensions[col].width = width
    del wb["Sheet"]
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    template = ws.review / f"decisions_{r.cycle}.csv"
    with template.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["proposal_id", "resolution", "value", "approver_role", "rationale"])
        for row in r.changes + r.excluded:
            w.writerow([row["proposal_id"], "", row["proposed"], "", ""])
        for row in r.holds:
            w.writerow([row["proposal_id"], "", "", "", ""])
    return path


def master_columns() -> list[str]:
    return MASTER_COLUMNS
