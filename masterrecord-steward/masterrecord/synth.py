"""The fictional Guild of Joiners & Finishers: a master workbook and three monthly feeds that disagree.

The master already has history (an earlier "Changes" tab) and reference rows far below the data, so
a write-back that disturbs anything it should not is easy to detect. The feeds plant one case of each
situation the steward has to handle.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

MASTER_COLUMNS = ["Entity ID", "Workshop", "certification_class", "participation_status", "network_affiliation",
                  "workshop_type", "inspection_zone", "Scope", "Last changed"]
FIELDS = MASTER_COLUMNS[2:7]
REFERENCE_ROW = 500
NAMES = ["Alder", "Birch", "Cedar", "Damson", "Elder", "Fir", "Gean", "Holly", "Ilex", "Juniper", "Larch",
         "Maple", "Nutmeg", "Oak", "Pine", "Quince", "Rowan", "Sorb", "Teak", "Umbra", "Vine", "Walnut", "Yew",
         "Zelkova", "Ash", "Beech", "Cherry", "Hazel", "Lime", "Pear"]
SUFFIX = ["Joinery", "Finishers", "Turnery", "Restorers", "Bench Works"]
CYCLE = "2026-11"

# what each planted entity demonstrates
PLANTED = {
    "GJF-0003": "registry upgrades the certification; the contract feed still has the old class (authority wins)",
    "GJF-0005": "contract and registry disagree on network affiliation (no authority) -> HOLD",
    "GJF-0008": "two site inspections give different inspection zones -> HOLD (conflicting location codes)",
    "GJF-0011": "registry silent on workshop type; site and contract disagree -> HOLD (ambiguous classification)",
    "GJF-0014": "no source gives a certification class -> HOLD as UNKNOWN (missing credential)",
    "GJF-0017": "registry reclassifies it as a retail showroom -> EXCLUDE (out of scope)",
    "GJF-0020": "no zone anywhere; zone filled from the postcode fallback map",
    "GJF-0022": "participation lapses",
    "GJF-0023": "certification withdrawn: 'none' means ineligible, not unknown",
    "GJF-0025": "the contract feed repeats the same row (duplicate update, ignored once)",
    "GJF-0027": "contract moves the workshop to another network",
}


def _master_rows(rng: random.Random) -> list[list]:
    rows = []
    for i in range(1, 31):
        rows.append([f"GJF-{i:04d}", f"{NAMES[i - 1]} {rng.choice(SUFFIX)}",
                     rng.choice(["Journeyman", "Master", "Fellow"]), "active",
                     rng.choice(["Northern Circle", "Coastal Ring", "Inland Bench", "independent"]),
                     rng.choice(["joinery", "finishing", "turning", "restoration"]),
                     rng.choice(["Z1", "Z2", "Z3", "Z4", "Z5"]), "in", "2026-10-26"])
    return rows


def build_master(path: Path, seed: int = 20261123) -> list[list]:
    rng = random.Random(seed)
    rows = _master_rows(rng)
    by_id = {r[0]: r for r in rows}
    by_id["GJF-0003"][2] = "Journeyman"
    by_id["GJF-0014"][2] = ""
    by_id["GJF-0020"][6] = ""
    by_id["GJF-0011"][5] = "joinery"
    by_id["GJF-0008"][6] = "Z3"
    by_id["GJF-0027"][4] = "Inland Bench"
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    for line in ["Guild of Joiners & Finishers - certified workshop master (FICTIONAL, SYNTHETIC)",
                 "Edit only through the steward process. Each approved change is listed on a dated Changes tab.",
                 "Reference rows at the foot of the Master tab must stay where they are."]:
        ins.append([line])
    ins["A1"].font = Font(bold=True, size=13)
    master = wb.create_sheet("Master")
    master.append(MASTER_COLUMNS)
    for cell in master[1]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="5B3A29")
    for row in rows:
        master.append(row)
    master.cell(row=REFERENCE_ROW, column=1, value="REFERENCE - do not move or delete")
    master.cell(row=REFERENCE_ROW + 1, column=1, value="Zones Z1-Z5 are defined on the Reference tab")
    master.cell(row=REFERENCE_ROW + 2, column=1, value="Scope 'excluded' rows stay for audit; they are not published")
    ref = wb.create_sheet("Reference")
    ref.append(["Zone", "Meaning"])
    for z, meaning in [("Z1", "Quayside"), ("Z2", "Mill race"), ("Z3", "Ridge"), ("Z4", "South fields"),
                       ("Z5", "Far ward")]:
        ref.append([z, meaning])
    old = wb.create_sheet("Changes 2026-10-26")
    old.append(["Entity ID", "Field", "Old", "New", "Decision", "Approver role", "Rationale"])
    old.append(["GJF-0002", "network_affiliation", "independent", rows[1][4], "P-old-1", "guild registrar",
                "joined a network"])
    for sheet, widths in ((master, (11, 22, 18, 18, 18, 16, 14, 9, 13)), (old, (11, 22, 16, 16, 32, 17, 48))):
        for col, width in zip("ABCDEFGHI", widths, strict=False):
            sheet.column_dimensions[col].width = width
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return rows


def write_feeds(folder: Path, master_rows: list[list]) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    m = {r[0]: dict(zip(MASTER_COLUMNS, r, strict=True)) for r in master_rows}
    stamp = "2026-11-20"
    registry, contract, site = [], [], []
    for eid, r in m.items():
        registry.append({"entity_id": eid, "workshop_name": r["Workshop"],
                         "certification_class": r["certification_class"],
                         "participation_status": "active", "network_affiliation": r["network_affiliation"],
                         "workshop_type": r["workshop_type"], "inspection_zone": r["inspection_zone"],
                         "observed_at": stamp})
        contract.append({"entity_id": eid, "network_affiliation": r["network_affiliation"],
                         "certification_class": r["certification_class"], "workshop_type": r["workshop_type"],
                         "observed_at": stamp})
        site.append({"entity_id": eid, "workshop_type": r["workshop_type"], "inspection_zone": r["inspection_zone"],
                     "postcode_token": "QA", "observed_at": "2026-11-12"})
    reg = {r["entity_id"]: r for r in registry}
    con = {r["entity_id"]: r for r in contract}
    sit = {r["entity_id"]: r for r in site}
    reg["GJF-0003"]["certification_class"] = "Master"
    con["GJF-0005"]["network_affiliation"] = "Coastal Ring"
    reg["GJF-0005"]["network_affiliation"] = "Northern Circle"
    reg["GJF-0008"]["inspection_zone"] = ""
    sit["GJF-0008"]["inspection_zone"] = "Z2"
    site.append({**sit["GJF-0008"], "inspection_zone": "Z4", "observed_at": "2026-11-18"})
    reg["GJF-0011"]["workshop_type"] = ""
    sit["GJF-0011"]["workshop_type"] = "joinery"
    con["GJF-0011"]["workshop_type"] = "finishing"
    reg["GJF-0014"]["certification_class"] = con["GJF-0014"]["certification_class"] = ""
    reg["GJF-0017"]["workshop_type"] = "retail showroom"
    sit["GJF-0017"]["workshop_type"] = con["GJF-0017"]["workshop_type"] = ""
    reg["GJF-0020"]["inspection_zone"] = sit["GJF-0020"]["inspection_zone"] = ""
    sit["GJF-0020"]["postcode_token"] = "SA"
    reg["GJF-0022"]["participation_status"] = "lapsed"
    reg["GJF-0023"]["certification_class"] = con["GJF-0023"]["certification_class"] = "none"
    contract.append(dict(con["GJF-0025"]))
    con["GJF-0027"]["network_affiliation"] = "Northern Circle"
    reg["GJF-0027"]["network_affiliation"] = ""
    paths = {}
    for name, rows in (("registry", registry), ("contract", contract), ("site", site)):
        path = folder / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        paths[name] = path
    return paths
