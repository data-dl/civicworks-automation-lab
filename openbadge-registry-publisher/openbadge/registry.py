"""Build the public registry from the database, serialise it canonically, and check it.

Canonical JSON (sorted keys, no spaces, UTF-8, one trailing newline) means the same data always gives
the same bytes, so a SHA-256 of the file identifies its content. Checks come in three layers:
the JSON Schema (shape), semantic rules (each record makes sense), and the delta against the release
consumers currently see (nothing vanished unexpectedly).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import jsonschema

from .runkit import SYNTHETIC_NOTICE

SCHEMA_PATH = Path(__file__).with_name("registry.schema.json")
MAX_DROP_FRACTION = 0.20


@dataclass
class Finding:
    rule: str
    severity: str  # blocking | advisory
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def build_payload(con: sqlite3.Connection, release_id: str, as_of: date) -> dict:
    # LEFT JOINs on purpose: an inner join would silently drop a badge whose type or learner is unknown, and a
    # record that vanishes can never be flagged. Keeping it lets validate() block the release and name it.
    rows = con.execute(
        "SELECT b.badge_id, COALESCE(l.alias, ''), b.badge_type, COALESCE(t.label, ''), b.issue_date, b.expiry_date "
        "FROM badge b LEFT JOIN learner l ON l.learner_id = b.learner_id "
        "LEFT JOIN badge_type t ON t.code = b.badge_type "
        "WHERE b.status = 'approved' ORDER BY b.badge_id, b.row_id").fetchall()
    badges = [{"badge_id": r[0], "learner_alias": r[1], "badge_type": r[2], "label": r[3], "issued": r[4],
               "expires": r[5]} for r in rows]
    return {"schema_version": "1.0", "registry": "Lantern Skills Academy (fictional)", "release_id": release_id,
            "as_of": as_of.isoformat(), "notice": SYNTHETIC_NOTICE, "record_count": len(badges), "badges": badges}


def canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _parse(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def validate(payload: dict, known_types: set[str], previous: dict | None = None,
             accept_drop: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    validator = jsonschema.Draft202012Validator(schema())
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.path))[:10]:
        where = "/".join(str(p) for p in error.path) or "(root)"
        findings.append(Finding("schema", "blocking", f"{where}: {error.message}"))

    badges = payload.get("badges", [])
    if payload.get("record_count") != len(badges):
        findings.append(Finding("record_count", "blocking",
                                f"record_count {payload.get('record_count')} but {len(badges)} badges"))
    seen: dict[str, int] = {}
    as_of = _parse(payload.get("as_of", "")) or date.max
    for badge in badges:
        seen[badge["badge_id"]] = seen.get(badge["badge_id"], 0) + 1
        issued, expires = _parse(badge["issued"]), _parse(badge["expires"])
        if issued is None or expires is None:
            findings.append(Finding("valid_dates", "blocking",
                                    f"{badge['badge_id']}: not a real date ({badge['issued']} / {badge['expires']})"))
        elif expires <= issued:
            findings.append(Finding("valid_dates", "blocking", f"{badge['badge_id']}: expires before it was issued"))
        elif issued > as_of:
            findings.append(Finding("valid_dates", "blocking", f"{badge['badge_id']}: issued after the release date"))
        if not badge["learner_alias"]:
            findings.append(Finding("known_learner", "blocking",
                                    f"{badge['badge_id']}: learner is not in the registry"))
        if badge["badge_type"] not in known_types:
            findings.append(Finding("controlled_vocabulary", "blocking",
                                    f"{badge['badge_id']}: unknown badge type {badge['badge_type']}"))
    for badge_id, count in sorted(seen.items()):
        if count > 1:
            findings.append(Finding("unique_badge_id", "blocking", f"{badge_id} appears {count} times"))

    if previous:
        before = {b["badge_id"] for b in previous.get("badges", [])}
        dropped = before - set(seen)
        added = set(seen) - before
        if before and len(dropped) / len(before) > MAX_DROP_FRACTION and not accept_drop:
            findings.append(Finding("release_delta", "blocking",
                                    f"{len(dropped)} of {len(before)} badges would disappear; rerun with "
                                    "--accept-drop if intended"))
        elif dropped:
            findings.append(Finding("release_delta", "advisory", f"{len(dropped)} badges leave the registry"))
        if added:
            findings.append(Finding("release_delta", "advisory", f"{len(added)} badges join the registry"))
    return findings


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "blocking"]
