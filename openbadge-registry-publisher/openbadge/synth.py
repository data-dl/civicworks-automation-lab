"""Synthetic learners and badges for the fictional Lantern Skills Academy, from a fixed seed.

Learners have invented aliases (adjective-animal-number), never names. Badge types, validity periods
and identifiers are made up. Scenario functions plant one defect each so the release checks have
something real to catch.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta

BADGE_TYPES = [
    ("KILN-SAFETY", "Kiln safety", 730),
    ("LOOM-TECH-1", "Loom technician, level 1", 1095),
    ("LOOM-TECH-2", "Loom technician, level 2", 1095),
    ("GLAZE-CHEM", "Glaze chemistry", 730),
    ("TIMBER-JOINT", "Timber jointing", 1460),
    ("LEATHER-TOOL", "Leather tooling", 1095),
    ("SCREEN-PRINT", "Screen printing", 730),
    ("RISO-OPS", "Risograph operation", 365),
    ("LETTERPRESS", "Letterpress composition", 1460),
    ("CERAMIC-RESTORE", "Ceramic restoration", 1095),
    ("METAL-PATINA", "Metal patination", 730),
    ("FIBER-DYE", "Natural fibre dyeing", 730),
]
ADJECTIVES = ["amber", "brisk", "cobalt", "dune", "ember", "fern", "granite", "hazel", "indigo", "juniper",
              "kelp", "lumen", "moss", "nimbus", "ochre", "pebble", "quill", "russet", "slate", "tidal"]
ANIMALS = ["heron", "otter", "lynx", "wren", "marten", "ibis", "newt", "plover", "stoat", "vole",
           "egret", "finch", "gecko", "hare", "koi", "loon", "moth", "puffin", "skink", "teal"]


def seed_database(con: sqlite3.Connection, seed: int = 20261123, learners: int = 120,
                  as_of: date = date(2026, 11, 23)) -> dict:
    rng = random.Random(seed)
    con.executemany("INSERT INTO badge_type (code, label, validity_days) VALUES (?, ?, ?)", BADGE_TYPES)
    aliases = set()
    learner_rows = []
    while len(learner_rows) < learners:
        alias = f"{rng.choice(ADJECTIVES)}-{rng.choice(ANIMALS)}-{rng.randrange(1000):03d}"
        if alias in aliases:
            continue
        aliases.add(alias)
        learner_rows.append((f"L{len(learner_rows) + 1:05d}", alias))
    con.executemany("INSERT INTO learner (learner_id, alias) VALUES (?, ?)", learner_rows)

    badges = []
    for learner_id, _ in learner_rows:
        for code, _, days in rng.sample(BADGE_TYPES, rng.randint(1, 4)):
            issued = as_of - timedelta(days=rng.randint(10, days - 5))
            status = rng.choices(["approved", "revoked", "pending"], weights=[88, 5, 7])[0]
            badges.append((f"LSA-{rng.getrandbits(32):08X}", learner_id, code, issued.isoformat(),
                           (issued + timedelta(days=days)).isoformat(), status))
    con.executemany("INSERT INTO badge (badge_id, learner_id, badge_type, issue_date, expiry_date, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)", badges)
    con.commit()
    return {"learners": len(learner_rows), "badges": len(badges), "seed": seed}


def plant_duplicate(con: sqlite3.Connection) -> str:
    """Copy one approved badge so the same badge_id appears twice."""
    row = con.execute("SELECT * FROM badge WHERE status = 'approved' ORDER BY row_id LIMIT 1 OFFSET 7").fetchone()
    con.execute("INSERT INTO badge (badge_id, learner_id, badge_type, issue_date, expiry_date, status) "
                "VALUES (?, ?, ?, ?, ?, 'approved')",
                (row["badge_id"], row["learner_id"], row["badge_type"], row["issue_date"], row["expiry_date"]))
    con.commit()
    return row["badge_id"]


def plant_invalid_date(con: sqlite3.Connection) -> str:
    """Make one approved badge expire before it was issued."""
    row = con.execute("SELECT * FROM badge WHERE status = 'approved' ORDER BY row_id LIMIT 1 OFFSET 19").fetchone()
    con.execute("UPDATE badge SET expiry_date = '2019-02-30' WHERE row_id = ?", (row["row_id"],))
    con.commit()
    return row["badge_id"]


def repair_planted(con: sqlite3.Connection) -> dict:
    """What a data steward would do: drop the copied row and restore the expiry from the badge type."""
    removed = con.execute(
        "DELETE FROM badge WHERE row_id IN (SELECT row_id FROM badge b WHERE EXISTS ("
        " SELECT 1 FROM badge o WHERE o.badge_id = b.badge_id AND o.row_id < b.row_id))").rowcount
    fixed = 0
    for row in con.execute("SELECT b.row_id, b.issue_date, t.validity_days FROM badge b "
                           "JOIN badge_type t ON t.code = b.badge_type WHERE b.expiry_date = '2019-02-30'").fetchall():
        expiry = date.fromisoformat(row["issue_date"]) + timedelta(days=row["validity_days"])
        con.execute("UPDATE badge SET expiry_date = ? WHERE row_id = ?", (expiry.isoformat(), row["row_id"]))
        fixed += 1
    con.commit()
    return {"duplicates_removed": removed, "dates_fixed": fixed}


def issue_new_badges(con: sqlite3.Connection, seed: int, count: int = 12, as_of: date = date(2026, 11, 23)) -> int:
    """A month's worth of new approvals, so the next release differs from the last."""
    rng = random.Random(seed)
    learners = [r[0] for r in con.execute("SELECT learner_id FROM learner ORDER BY learner_id")]
    rows = []
    for _ in range(count):
        code, _, days = rng.choice(BADGE_TYPES)
        issued = as_of - timedelta(days=rng.randint(0, 6))
        rows.append((f"LSA-{rng.getrandbits(32):08X}", rng.choice(learners), code, issued.isoformat(),
                     (issued + timedelta(days=days)).isoformat()))
    con.executemany("INSERT INTO badge (badge_id, learner_id, badge_type, issue_date, expiry_date, status) "
                    "VALUES (?, ?, ?, ?, ?, 'approved')", rows)
    con.commit()
    return len(rows)
