"""Ingest, normalise, check and freeze.

    ingest     each source file is hashed, counted and its columns checked before anything is read
    normalise  crafts mapped to codes, phone numbers to one format, districts to known codes - the raw
               value is always kept beside the clean one; repeated rows collapse to one
    check      every rule in rules.yaml runs; findings carry the rule, the records and the fix
    freeze     only a clean, named approval turns the tables into a read-only snapshot for printing
"""

from __future__ import annotations

import csv
import difflib
import re
import sqlite3
import stat
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .db import connect, migrate
from .runkit import sha256_file, utc_now, write_json
from .synth import CRAFTS, DISTRICTS, SPELLINGS

RULES_FILE = Path(__file__).with_name("rules.yaml")
EXPECTED = {"members": ["member_id", "name", "phone", "state", "public_opt_in"],
            "studios": ["studio_id", "studio_name", "district", "venue_token"],
            "endorsements": ["endorsement_id", "member_id", "craft", "valid_from", "valid_to"],
            "listings": ["member_id", "studio_id", "edition", "approved"]}
SIMILAR = 0.92


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    db = property(lambda self: self.root / "atlas.sqlite")
    sources = property(lambda self: self.root / "sources")
    qa = property(lambda self: self.root / "qa")
    snapshots = property(lambda self: self.root / "snapshots")
    staging = property(lambda self: self.root / "staging")
    published = property(lambda self: self.root / "published")
    runs = property(lambda self: self.root / "runs")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


@dataclass
class Finding:
    rule: str
    severity: str
    records: list[str]
    detail: str
    remediation: str = ""


@dataclass
class CheckResult:
    period: str
    counts: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocking"]


def release_date(period: str) -> date:
    year, month = map(int, period.split("-"))
    return date(year + (month == 12), 1 if month == 12 else month + 1, 1)


def phone_token(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else "unknown"


def craft_code(raw: str) -> str | None:
    key = " ".join(raw.lower().split())
    for code, spellings in SPELLINGS.items():
        if key in {s.lower() for s in spellings}:
            return code
    return None


def _parse(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def load_rules() -> dict[str, dict]:
    return {r["id"]: r for r in yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))["rules"]}


def ingest_and_check(ws: Workspace, period: str) -> CheckResult:
    rules = load_rules()
    result = CheckResult(period)
    con = ws.open()

    def find(rule: str, records: list[str], detail: str) -> None:
        r = rules[rule]
        result.findings.append(Finding(rule, r["severity"], records, detail, r["remediation"]))

    rows: dict[str, list[dict]] = {}
    for name, columns in EXPECTED.items():
        path = ws.sources / period / f"{name}.csv"
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != columns:
                raise ValueError(f"{name}.csv columns {reader.fieldnames} != expected {columns}")
            rows[name] = list(reader)
        con.execute("INSERT OR REPLACE INTO source_file VALUES (?, ?, ?, ?, ?, ?)",
                    (name, period, sha256_file(path), len(rows[name]), ",".join(columns), utc_now()))
        result.counts[name] = len(rows[name])

    for table in ("placement", "endorsement", "studio", "guild_member", "craft", "district"):
        con.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
    con.execute("DELETE FROM review_candidate WHERE period = ?", (period,))
    con.executemany("INSERT INTO district VALUES (?, ?)", DISTRICTS)
    con.executemany("INSERT INTO craft VALUES (?, ?)", CRAFTS)

    seen: dict[str, str] = {}
    for m in rows["members"]:
        if m["member_id"] in seen:
            find("duplicate_member_id", [m["member_id"]],
                 f"{m['member_id']} is both '{seen[m['member_id']]}' and '{m['name']}'")
            continue
        seen[m["member_id"]] = m["name"]
        con.execute("INSERT INTO guild_member VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (m["member_id"], " ".join(m["name"].split()), m["name"], phone_token(m["phone"]), m["phone"],
                     m["state"], int(m["public_opt_in"])))
    districts = {d[0] for d in DISTRICTS}
    for s in rows["studios"]:
        known = s["district"] if s["district"] in districts else None
        if known is None:
            find("orphaned_studio", [s["studio_id"]], f"{s['studio_id']} is in district '{s['district']}', "
                                                      "which does not exist")
        if not s["venue_token"].strip():
            find("missing_venue_token", [s["studio_id"]], f"{s['studio_id']} has no venue token")
        con.execute("INSERT INTO studio VALUES (?, ?, ?, ?, ?)",
                    (s["studio_id"], known, s["district"], s["studio_name"], s["venue_token"].strip()))
    cutoff = release_date(period)
    valid_endorsement: set[str] = set()
    for e in rows["endorsements"]:
        code = craft_code(e["craft"])
        if code is None:
            find("unknown_craft", [e["endorsement_id"]], f"{e['endorsement_id']}: craft '{e['craft']}' "
                                                         "matches no known craft")
        start, end = _parse(e["valid_from"]), _parse(e["valid_to"])
        if start is None or end is None or end <= start:
            find("invalid_dates", [e["endorsement_id"]], f"{e['endorsement_id']}: {e['valid_from']} to "
                                                         f"{e['valid_to']} is not a real date range")
        elif end < cutoff:
            find("expired_endorsement", [e["member_id"], e["endorsement_id"]],
                 f"{e['member_id']}'s endorsement {e['endorsement_id']} ends {end}, before the {cutoff} edition")
        else:
            valid_endorsement.add(e["member_id"])
        if e["member_id"] in seen:
            con.execute("INSERT INTO endorsement VALUES (?, ?, ?, ?, ?, ?)",
                        (e["endorsement_id"], e["member_id"], code, e["craft"], e["valid_from"], e["valid_to"]))

    opt_in = {m["member_id"]: m["public_opt_in"] for m in rows["members"]}
    keys, repeats = set(), 0
    endorsed = {r[0] for r in con.execute("SELECT DISTINCT member_id FROM endorsement")}
    for p in rows["listings"]:
        key = (p["member_id"], p["studio_id"], p["edition"])
        if key in keys:
            repeats += 1
            continue
        keys.add(key)
        if p["member_id"] not in endorsed:
            find("missing_endorsement", [p["member_id"]], f"{p['member_id']} is listed but has no endorsement")
        if p["edition"] == "public" and opt_in.get(p["member_id"]) == "0":
            find("contradictory_audience", [p["member_id"]],
                 f"{p['member_id']} is placed in the public edition but did not opt in")
        if p["member_id"] in seen:
            con.execute("INSERT INTO placement VALUES (?, ?, ?, ?, ?)",
                        ("-".join(key), *key, int(p["approved"])))
    if repeats:
        result.notes.append(f"{repeats} repeated listing row(s) collapsed by their key (member, studio, edition)")
    result.notes.append(f"{sum(1 for e in rows['endorsements'] if craft_code(e['craft']))} craft spellings mapped "
                        f"to {len(CRAFTS)} codes; phone numbers put in one format")

    names = sorted(seen.items())
    for i, (id_a, a) in enumerate(names):
        for id_b, b in names[i + 1:]:
            score = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
            if score >= SIMILAR and a != b:
                con.execute("INSERT INTO review_candidate (period, member_a, member_b, similarity, evidence) "
                            "VALUES (?, ?, ?, ?, ?)", (period, id_a, id_b, round(score, 3), f"'{a}' vs '{b}'"))
                find("possible_duplicate_person", [id_a, id_b], f"'{a}' ({id_a}) and '{b}' ({id_b}) are "
                                                                f"{score:.0%} alike - review, never merged")
    con.commit()
    con.close()
    write_qa_summary(ws, result)
    return result


def write_qa_summary(ws: Workspace, r: CheckResult) -> None:
    folder = ws.qa / r.period
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "qa_summary.json", {"period": r.period, "counts": r.counts, "notes": r.notes,
                                             "findings": [asdict(f) for f in r.findings],
                                             "blocking": len(r.blocking)})
    with (folder / "qa_findings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rule", "severity", "records", "detail", "remediation"])
        for x in r.findings:
            w.writerow([x.rule, x.severity, " ".join(x.records), x.detail, x.remediation])
    rows = "".join(f"<tr class='{x.severity}'><td>{x.severity}</td><td>{x.rule}</td><td>{', '.join(x.records)}</td>"
                   f"<td>{x.detail}</td><td>{x.remediation}</td></tr>" for x in r.findings)
    (folder / "qa_summary.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Atlas QA " + r.period + "</title><style>body{font:14px "
        "system-ui;margin:24px;color:#1d2733}table{border-collapse:collapse}td,th{border:1px solid #d9e0e7;"
        "padding:4px 8px;text-align:left}.blocking td:first-child{color:#a8322d;font-weight:600}</style>"
        f"<h1>Atlas QA summary - {r.period}</h1><p>DEMO / SYNTHETIC. {len(r.blocking)} blocking, "
        f"{len(r.findings) - len(r.blocking)} advisory.</p><table><tr><th>severity</th><th>rule</th>"
        f"<th>records</th><th>detail</th><th>fix</th></tr>{rows}</table>", encoding="utf-8")


def freeze(ws: Workspace, period: str, approve_as: str | None) -> tuple[bool, str]:
    """Copy the checked tables into a read-only snapshot. Needs no blocking findings and a named approver."""
    summary = ws.qa / period / "qa_summary.json"
    if not summary.exists():
        return False, "run the checks first"
    import json

    blocking = json.loads(summary.read_text(encoding="utf-8"))["blocking"]
    if blocking:
        return False, f"{blocking} blocking finding(s) - nothing can be frozen"
    if not approve_as:
        return False, "checks pass; a directory editor must approve before the snapshot is frozen (--approve ROLE)"
    target = ws.snapshots / period / "snapshot.sqlite"
    if target.exists():
        return False, f"{period} is already frozen; a frozen snapshot is never replaced"
    target.parent.mkdir(parents=True, exist_ok=True)
    src = ws.open()
    dst = sqlite3.connect(target)
    src.backup(dst)
    dst.close()
    target.chmod(stat.S_IREAD)
    digest = sha256_file(target)
    src.execute("INSERT OR REPLACE INTO directory_release (release_id, period, stage, snapshot_hash, approved_by, "
                "updated_at) VALUES (?, ?, 'frozen', ?, ?, ?)", (period, period, digest, approve_as, utc_now()))
    src.commit()
    src.close()
    return True, f"snapshot frozen read-only, sha256 {digest[:12]}, approved by {approve_as}"
