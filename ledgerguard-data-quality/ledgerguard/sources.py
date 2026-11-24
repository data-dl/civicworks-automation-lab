"""The fictional Ledger Equipment Cooperative's three source systems, and the adapters that read them.

    registry.sqlite        equipment and the class each item belongs to (read with SQL)
    roster.csv             technicians, their depot and whether they are marked active
    authorizations.csv     which equipment classes each technician may service, and until when
    desk app               an old desktop program whose only way out is an "Export" button; here a mock
                           adapter writes its CSV, and can be told to misbehave the way such exports do

Every adapter returns rows plus the row count the source itself says it has, so a job can compare
what it expected with what it got.
"""

from __future__ import annotations

import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DEPOTS = ["Copperford", "Millbrae", "Stonegate", "Wharfside"]
CLASSES = {"EXC": "Mini excavator", "LFT": "Scissor lift", "GEN": "Generator", "CMP": "Compactor",
           "SAW": "Concrete saw", "PMP": "Water pump"}
EXPORT_COLUMNS = ["equipment_id", "class_code", "depot", "serial_token", "last_service", "status"]
RUN_DATE = date(2026, 11, 23)


def generate(folder: Path, seed: int = 20261123) -> dict:
    """Sources with four planted data problems for the jobs to find."""
    rng = random.Random(seed)
    folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(folder / "registry.sqlite")
    con.executescript("DROP TABLE IF EXISTS equipment; CREATE TABLE equipment (equipment_id TEXT PRIMARY KEY, "
                      "class_code TEXT NOT NULL, depot TEXT NOT NULL, serial_token TEXT, last_service TEXT, "
                      "status TEXT NOT NULL);")
    equipment = []
    for i in range(1, 121):
        code = list(CLASSES)[i % len(CLASSES)]
        depot = DEPOTS[(i // len(CLASSES)) % len(DEPOTS)]   # every class appears at every depot
        service = RUN_DATE - timedelta(days=rng.randint(5, 300))
        equipment.append([f"EQ-{i:04d}", code, depot, f"SN{rng.getrandbits(28):07X}", service.isoformat(),
                          rng.choice(["available", "on-rent", "on-rent", "in-repair"])])
    equipment[9][3] = ""                                   # problem: blank serial
    equipment[33][4] = ""                                  # problem: no service date
    equipment[50][3] = equipment[51][3]                    # problem: one serial under two classes
    con.executemany("INSERT INTO equipment VALUES (?, ?, ?, ?, ?, ?)", equipment)
    con.commit()
    con.close()

    techs, auths = [], []
    for i in range(1, 29):
        depot = DEPOTS[i % len(DEPOTS)]
        techs.append([f"T-{i:03d}", f"tech-{i:03d}", depot, "1"])
        for code in rng.sample(list(CLASSES), 3):
            auths.append([f"T-{i:03d}", code, (RUN_DATE + timedelta(days=rng.randint(30, 700))).isoformat()])
    # problem: an active technician whose every authorisation has lapsed
    auths = [a for a in auths if a[0] != "T-007"] + [["T-007", "GEN", "2026-08-31"], ["T-007", "PMP", "2026-10-15"]]
    # problem: nobody at Wharfside may service concrete saws
    auths = [a for a in auths if not (a[1] == "SAW" and techs[int(a[0][2:]) - 1][2] == "Wharfside")]
    for name, header, rows in (("roster", ["technician_id", "alias", "depot", "active"], techs),
                               ("authorizations", ["technician_id", "class_code", "expiry"], auths)):
        with (folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    return {"equipment": len(equipment), "technicians": len(techs), "authorizations": len(auths)}


class SqliteAdapter:
    name = "sqlite"

    def __init__(self, path: Path):
        self.path = path

    def equipment(self) -> tuple[list[dict], int]:
        con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute("SELECT * FROM equipment ORDER BY equipment_id")]
        count = con.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        con.close()
        return rows, count


class CsvAdapter:
    name = "csv"

    def __init__(self, path: Path):
        self.path = path

    def rows(self) -> tuple[list[dict], int]:
        with self.path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        return rows, len(rows)


class DeskAppExport:
    """Stands in for clicking Export in an old desktop program. The program always says 'Export complete';
    `mode` makes it do what such programs sometimes do instead of exporting properly."""

    name = "desk-app"
    MODES = ("normal", "empty", "renamed-column", "truncated")

    def __init__(self, registry: Path, mode: str = "normal"):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        self.registry, self.mode = registry, mode

    def export(self, target: Path) -> tuple[Path, int, str]:
        rows, count = SqliteAdapter(self.registry).equipment()
        columns = list(EXPORT_COLUMNS)
        if self.mode == "renamed-column":
            columns[3] = "serial_no"
        if self.mode == "empty":
            rows = []
        if self.mode == "truncated":
            rows = rows[: len(rows) // 3]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(columns)
            for r in rows:
                w.writerow([r[c] for c in EXPORT_COLUMNS])
        return target, count, "Export complete"   # what the program reports, whatever it actually did
