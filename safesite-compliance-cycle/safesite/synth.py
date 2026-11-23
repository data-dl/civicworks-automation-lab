"""The fictional Meridian Facilities Consortium and its coordinators' quarterly spreadsheets.

Twelve invented facilities in three invented districts, four coordinators known only by role. Each
facility's spreadsheet "arrives" on a scheduled day, so running the cycle as of different dates shows
reminders, corrections and late returns exactly as they would unfold.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

DISTRICTS = {"HW": "Harbor Ward", "MD": "Mill District", "RQ": "Ridge Quarter"}
WORKSHOP_TYPES = ["Joinery Workshop", "Ceramics Studio", "Metal Shop", "Print Studio"]
DEPOT_TYPES = ["Cold Store Depot", "Parts Warehouse"]
AREAS = {"workshop": ["bench room", "spray booth", "kiln yard", "tool store", "dust extraction"],
         "depot": ["loading bay", "racking aisle", "forklift lane", "cold room", "yard gate"]}
FINDINGS = {"S1": ["housekeeping note", "signage faded"], "S2": ["guard loose", "trip hazard taped"],
            "S3": ["extraction below rated flow", "blocked fire exit"], "S4": ["live conductor exposed"]}
COORDINATORS = [("C1", "Harbor Ward coordinator", "coordinator.harbor@example.org"),
                ("C2", "Mill District coordinator", "coordinator.mill@example.org"),
                ("C3", "Ridge Quarter coordinator", "coordinator.ridge@example.org"),
                ("C4", "Depots coordinator", "coordinator.depots@example.org")]
QUARTER = "2026Q4"
DUE = date(2026, 12, 15)
QUARTER_START = date(2026, 10, 1)

# facility -> (arrival day of v1, problem planted in v1, arrival day of the corrected v2)
SCHEDULE = {
    "F01": (date(2026, 11, 28), None, None),
    "F02": (date(2026, 11, 28), None, None),
    "F03": (date(2026, 11, 29), "missing_evidence", date(2026, 12, 10)),
    "F04": (date(2026, 11, 30), None, None),
    "F05": (date(2026, 11, 30), "totals_mismatch", date(2026, 12, 11)),
    "F06": (date(2026, 12, 9), None, None),
    "F07": (date(2026, 12, 10), None, None),
    "F08": (date(2026, 11, 30), "bad_severity", date(2026, 12, 10)),
    "F09": (date(2026, 12, 12), None, None),
    "F10": (date(2026, 12, 14), None, None),
    "F11": (date(2026, 12, 19), None, None),
    "F12": (date(2026, 12, 19), None, None),
}


def build_consortium(con: sqlite3.Connection, seed: int = 20261123) -> list[tuple]:
    rng = random.Random(seed)
    facilities = []
    n = 0
    for code, district in DISTRICTS.items():
        for kind in rng.sample(WORKSHOP_TYPES, 3):
            n += 1
            facilities.append((f"F{n:02d}", f"{district} {kind}", code, "workshop"))
    for code, district in DISTRICTS.items():
        n += 1
        facilities.append((f"F{n:02d}", f"{district} {rng.choice(DEPOT_TYPES)}", code, "depot"))
    con.executemany("INSERT INTO facility VALUES (?, ?, ?, ?)", facilities)
    con.executemany("INSERT INTO coordinator VALUES (?, ?, ?)", COORDINATORS)
    con.commit()
    return facilities


def _observations(rng: random.Random, facility_id: str, category: str, problem: str | None) -> list[list]:
    rows = []
    for i in range(rng.randint(4, 9)):
        severity = rng.choices(["S1", "S2", "S3", "S4"], weights=[45, 35, 15, 5])[0]
        if i == 0:
            severity = "S3"  # every return has at least one significant finding to report on
        observed = QUARTER_START + timedelta(days=rng.randint(0, 60))
        evidence = f"PHOTO-{facility_id}-{i + 1:02d}" if severity in ("S3", "S4") or rng.random() < 0.3 else ""
        rows.append([f"{facility_id}-O{i + 1:02d}", observed.isoformat(), rng.choice(AREAS[category]), severity,
                     rng.choice(FINDINGS[severity]), rng.choice(["open", "in-progress", "closed"]), evidence])
    if problem == "missing_evidence":
        rows[0][6] = ""
    if problem == "bad_severity":
        rows[1][3] = "HIGH"
    return rows


def write_return(path: Path, facility_id: str, category: str, seed: int, problem: str | None) -> Path:
    rng = random.Random(f"{seed}-{facility_id}")
    rows = _observations(rng, facility_id, category, problem)
    wb = Workbook()
    ws = wb.active
    ws.title = "Observations"
    ws.append(["Observation ID", "Date", "Area", "Severity", "Description", "Action", "Evidence ref"])
    for row in rows:
        ws.append(row)
    totals = wb.create_sheet("Totals")
    totals.append(["Severity", "Count"])
    for sev in ("S1", "S2", "S3", "S4"):
        count = sum(1 for r in rows if r[3] == sev)
        totals.append([sev, count + (2 if problem == "totals_mismatch" and sev == "S1" else 0)])
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def deliver(submissions: Path, facilities: list[tuple], as_of: date, seed: int) -> list[str]:
    """Write every return that has 'arrived' by `as_of` and is not already there."""
    categories = {f[0]: f[3] for f in facilities}
    arrived = []
    for facility_id, (day, problem, fixed_on) in SCHEDULE.items():
        versions = [(1, day, problem)] + ([(2, fixed_on, None)] if fixed_on else [])
        for version, when, issue in versions:
            path = submissions / QUARTER / f"{facility_id}_v{version}.xlsx"
            if when <= as_of and not path.exists():
                write_return(path, facility_id, categories[facility_id], seed, issue)
                arrived.append(path.name)
    return arrived
