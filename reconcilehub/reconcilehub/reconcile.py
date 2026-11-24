"""Monthly reconciliation: what the access system has, against what was approved and newly registered.

Identifiers are normalised (spaces, case, padding) but the original value is always kept. Exact id
matches are decided automatically. Anything that would need a guess - an id that seems to have
changed, a row with no id, a registration that looks like an existing member - becomes a held case
with a suggestion and a confidence, and waits for a person. Nothing is merged automatically.
"""

from __future__ import annotations

import csv
import difflib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .db import connect, migrate
from .runkit import sha256_bytes, sha256_file

ID_PATTERN = re.compile(r"^FC-?(\d{1,5})$")
MATCH_THRESHOLD = 0.88


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    db = property(lambda self: self.root / "reconcile.sqlite")
    inputs = property(lambda self: self.root / "inputs")
    snapshots = property(lambda self: self.root / "snapshots")
    exports = property(lambda self: self.root / "exports")
    outbox = property(lambda self: self.root / "outbox")
    runs = property(lambda self: self.root / "runs")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


def norm_id(raw: str) -> str | None:
    match = ID_PATTERN.match((raw or "").strip().upper().replace(" ", ""))
    return f"FC-{int(match.group(1)):05d}" if match else None


def norm_name(raw: str) -> str:
    text = unicodedata.normalize("NFKD", raw or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold().replace("-", " ")
    return " ".join(text.split())


def similarity(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, norm_name(a), norm_name(b)).ratio(), 3)


@dataclass
class Case:
    case_id: str
    kind: str
    old_ref: str
    new_ref: str
    confidence: float
    detail: str
    disposition: str = "held"


@dataclass
class Recon:
    cycle: str
    unchanged: int = 0
    normalised_ids: int = 0
    actions: list[dict] = field(default_factory=list)     # ADD / REMOVE / CHANGE ROLE / RENAME ID / FIX ID
    cases: list[Case] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    approved: dict[str, dict] = field(default_factory=dict)

    @property
    def held(self) -> list[Case]:
        return [c for c in self.cases if c.disposition == "held"]


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _store_snapshot(con: sqlite3.Connection, cycle: str, source: str, path: Path, rows: list[dict]) -> None:
    sha = sha256_file(path)
    if con.execute("SELECT 1 FROM roster_snapshot WHERE cycle = ? AND source_code = ? AND sha256 = ?",
                   (cycle, source, sha)).fetchone():
        return
    sid = con.execute("INSERT INTO roster_snapshot (cycle, source_code, sha256) VALUES (?, ?, ?)",
                      (cycle, source, sha)).lastrowid
    for r in rows:
        raw = r.get("member_id", "")
        pid = norm_id(raw)
        if pid:
            con.execute("INSERT OR IGNORE INTO participant VALUES (?, ?)", (pid, r["display_name"]))
        role = r.get("access_role") or r.get("requested_role")
        con.execute("INSERT INTO roster_entry (snapshot_id, participant_id, raw_id, display_name, space_code, "
                    "access_role) VALUES (?, ?, ?, ?, ?, ?)", (sid, pid, raw, r["display_name"], r["space_code"], role))


def reconcile(ws: Workspace, cycle: str) -> Recon:
    folder = ws.inputs / cycle
    current = _read(folder / "current_roster.csv")
    prior = _read(folder / "prior_approvals.csv")
    regs = _read(folder / "new_registrations.csv")
    con = ws.open()
    for source, path, rows in (("current", folder / "current_roster.csv", current),
                               ("prior", folder / "prior_approvals.csv", prior),
                               ("registrations", folder / "new_registrations.csv", regs)):
        _store_snapshot(con, cycle, source, path, rows)
    decided = {r["case_id"]: r["disposition"] for r in con.execute(
        "SELECT case_id, disposition FROM match_case WHERE cycle = ?", (cycle,))}
    r = Recon(cycle)

    def case(kind: str, old: str, new: str, conf: float, detail: str) -> Case:
        c = Case(f"{kind}:{old}->{new}", kind, old, new, conf, detail, decided.get(f"{kind}:{old}->{new}", "held"))
        r.cases.append(c)
        con.execute("INSERT INTO match_case (case_id, cycle, kind, old_ref, new_ref, confidence, detail) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(case_id) DO UPDATE SET detail = excluded.detail",
                    (c.case_id, cycle, kind, old, new, conf, detail))
        return c

    approved = {norm_id(p["member_id"]): p for p in prior}
    expected = {k: {"name": v["display_name"], "space": v["space_code"], "role": v["access_role"], "why": "approved"}
                for k, v in approved.items()}
    for g in regs:
        pid = norm_id(g["member_id"])
        if pid:
            expected[pid] = {"name": g["display_name"], "space": g["space_code"], "role": g["requested_role"],
                             "why": f"registration {g['registration_ref']}"}

    have: dict[str, dict] = {}
    no_id_rows = []
    for n, row in enumerate(current, start=2):
        pid = norm_id(row["member_id"])
        if pid is None:
            no_id_rows.append((n, row))
            continue
        if row["member_id"] != pid:
            r.normalised_ids += 1
        if pid in have:
            case("duplicate-id", pid, f"row {n}", 1.0, f"{pid} appears twice in the access system")
            continue
        have[pid] = {"name": row["display_name"], "space": row["space_code"], "role": row["access_role"],
                     "raw": row["member_id"]}

    missing = {k: v for k, v in expected.items() if k not in have}       # approved, not in the system
    unknown = {k: v for k, v in have.items() if k not in expected}       # in the system, not approved
    paired_old, paired_new = set(), set()
    for old, exp in sorted(missing.items()):                             # changed ids
        best = max(((similarity(exp["name"], v["name"]), new) for new, v in unknown.items()
                    if v["space"] == exp["space"]), default=(0, None))
        if best[0] >= MATCH_THRESHOLD:
            c = case("possible-id-change", old, best[1], best[0],
                     f"{exp['name']} ({old}) is missing; {unknown[best[1]]['name']} ({best[1]}) appeared in the same "
                     "space")
            if c.disposition != "different-person":   # held or excluded: touch neither side yet
                paired_old.add(old)
                paired_new.add(best[1])
            if c.disposition == "same-person":
                r.actions.append({"action": "RENAME ID", "member_id": best[1], "name": exp["name"],
                                  "space": exp["space"], "role": exp["role"], "reason": f"was {old}; {c.case_id}"})
                expected[best[1]] = {**exp, "why": f"renamed from {old}"}
                del expected[old]
                have.setdefault(best[1], unknown[best[1]])
    for n, row in no_id_rows:                                            # rows that lost their id
        best = max(((similarity(row["display_name"], v["name"]), k) for k, v in missing.items()
                    if k not in paired_old and v["space"] == row["space_code"]), default=(0, None))
        suggestion = best[1] if best[0] >= MATCH_THRESHOLD else "none"
        c = case("missing-id", suggestion, f"row {n}", best[0],
                 f"access-system row {n} ({row['display_name']}) has no member id; suggested {suggestion}")
        if suggestion != "none" and c.disposition in ("held", "exclude"):
            paired_old.add(suggestion)    # do not re-add the suggested member while the row is unexplained
        if c.disposition == "same-person" and suggestion != "none":
            r.actions.append({"action": "FIX ID", "member_id": suggestion, "name": row["display_name"],
                              "space": row["space_code"], "role": expected[suggestion]["role"],
                              "reason": f"row {n} had no id; {c.case_id}"})
            have[suggestion] = {"name": row["display_name"], "space": row["space_code"], "role": row["access_role"]}
            paired_old.add(suggestion)
    known = {**{k: v["name"] for k, v in expected.items()}, **{k: v["name"] for k, v in have.items()}}
    for g in regs:                                                       # registrations without an id
        if norm_id(g["member_id"]):
            continue
        best = max(((similarity(g["display_name"], name), k) for k, name in known.items()), default=(0, None))
        kind = "possible-duplicate" if best[0] >= MATCH_THRESHOLD else "needs-id"
        c = case(kind, best[1] or "none", g["registration_ref"], best[0],
                 f"{g['registration_ref']} '{g['display_name']}' has no member id"
                 + (f"; looks like {best[1]} {known[best[1]]} ({best[0]:.0%})" if kind == "possible-duplicate" else ""))
        if c.disposition == "same-person":
            r.notes.append(f"{g['registration_ref']} is existing member {best[1]}; no new access")

    names: dict[str, list[str]] = {}
    for k, v in expected.items():
        names.setdefault(norm_name(v["name"]), []).append(k)
    for ids_ in names.values():
        if len(ids_) > 1:
            r.notes.append(f"{' and '.join(sorted(ids_))} share a name; kept as different people (ids differ)")

    for pid, exp in sorted(expected.items()):
        if pid in paired_old and pid not in have:
            continue
        cur = have.get(pid)
        if cur is None:
            r.actions.append({"action": "ADD", "member_id": pid, "name": exp["name"], "space": exp["space"],
                              "role": exp["role"], "reason": exp["why"]})
        elif cur["role"] != exp["role"]:
            r.actions.append({"action": "CHANGE ROLE", "member_id": pid, "name": exp["name"], "space": exp["space"],
                              "role": exp["role"], "reason": f"system has {cur['role']}; approved {exp['role']}"})
        elif not any(a["member_id"] == pid for a in r.actions):
            r.unchanged += 1
        if cur is not None and norm_name(cur["name"]) != norm_name(exp["name"]):
            # Same id, different name: never a reason to change access, but a person should know.
            r.notes.append(f"{pid}: the access system says '{cur['name']}', the approval says '{exp['name']}' - "
                           "same member id, access unchanged; check the spelling")
        r.approved[pid] = {"name": exp["name"], "space": exp["space"], "role": exp["role"]}
    for pid, cur in sorted(have.items()):
        if pid not in expected and pid not in paired_new:
            r.actions.append({"action": "REMOVE", "member_id": pid, "name": cur["name"], "space": cur["space"],
                              "role": cur["role"], "reason": "not in last month's approvals or this month's "
                                                             "registrations"})
    con.commit()
    con.close()
    return r


def record_decisions(ws: Workspace, cycle: str, decisions: Path) -> list[str]:
    con = ws.open()
    problems = []
    with decisions.open(encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            if not row.get("disposition"):
                continue
            if row["disposition"] not in ("same-person", "different-person", "exclude") or not row.get("reviewer"):
                problems.append(f"line {n}: need a disposition (same-person/different-person/exclude) and a reviewer")
                continue
            updated = con.execute("UPDATE match_case SET disposition = ?, reviewer = ? WHERE case_id = ? AND cycle = ?",
                                  (row["disposition"], row["reviewer"], row["case_id"], cycle)).rowcount
            if not updated:
                problems.append(f"line {n}: no case {row['case_id']}")
    con.commit()
    con.close()
    return problems


def roster_bytes(approved: dict[str, dict]) -> bytes:
    lines = ["member_id,display_name,space_code,access_role"]
    lines += [f"{k},{v['name']},{v['space']},{v['role']}" for k, v in sorted(approved.items())]
    return ("\n".join(lines) + "\n").encode("utf-8")


def roster_sha(approved: dict[str, dict]) -> str:
    return sha256_bytes(roster_bytes(approved))
