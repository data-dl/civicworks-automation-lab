"""The fictional Foundry Commons federation: four maker spaces and three monthly inputs.

Names are built from invented fragments ("Bryn Copperwick") so they cannot be mistaken for real
people. The current roster comes from the access system as exported, with its usual mess: ids in lower
case without padding, a blank id, an id that changed, a member who should have been removed, a role
that drifted. One registration has no id and a name that nearly matches an existing member.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

GIVEN = ["Arlo", "Bryn", "Cass", "Dov", "Esme", "Fen", "Gil", "Hollis", "Ivo", "Jory", "Kit", "Lark", "Mabry",
         "Nell", "Oren", "Pim", "Quin", "Rue", "Sable", "Tam"]
FAMILY = ["Copperwick", "Tallowmere", "Quillbrook", "Emberfield", "Mossgrave", "Thistlemoor", "Larkspurne",
          "Fennimoss", "Ashgrove-Vale", "Brindlecote", "Cindervale", "Dunmarrow"]
SPACES = {"AY": "Anvil Yard", "BH": "Bobbin Hall", "CD": "Circuit Den", "DK": "Drift Kiln"}
ROLES = ["member", "steward", "trainer"]
CYCLE = "2026-11"
FIELDS = ["member_id", "display_name", "space_code", "access_role"]


def _write(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def build_inputs(folder: Path, seed: int = 20261123) -> dict:
    rng = random.Random(seed)
    names: set[str] = set()
    members = []
    while len(members) < 58:
        name = f"{rng.choice(GIVEN)} {rng.choice(FAMILY)}"
        if name in names:
            continue
        names.add(name)
        members.append([f"FC-{len(members) + 1:05d}", name, rng.choice(list(SPACES)),
                        rng.choices(ROLES, weights=[80, 15, 5])[0]])
    # two different people who share a name, in different spaces
    members.append(["FC-00059", members[4][1], "DK" if members[4][2] != "DK" else "AY", "member"])
    prior = [m + ["2026-10-31"] for m in members]

    current = [list(m) for m in members]
    planted = {}
    current[16][0] = " fc-17 "                                   # formatting only
    current[30][0] = "FC-00931"                                  # id changed in the access system
    planted["changed_id"] = f"FC-00031 -> FC-00931 ({members[30][1]})"
    current[40][0] = ""                                          # id lost in export
    planted["missing_id"] = members[40][1]
    current[12][3] = "steward" if members[12][3] != "steward" else "trainer"
    planted["role_drift"] = f"{members[12][0]} {members[12][3]} -> {current[12][3]} in the access system"
    gone = members[50]
    prior = [p for p in prior if p[0] != gone[0]]
    planted["should_be_revoked"] = f"{gone[0]} (not in last month's approvals)"

    near = members[8]
    registrations = [
        ["REG-2611-01", "Pim Hollowmere", "BH", "member", "FC-00060"],     # surnames outside FAMILY: new people
        ["REG-2611-02", "Sable Quarrywick", "CD", "trainer", "FC-00061"],
        ["REG-2611-03", near[1].replace(" ", "  ").lower(), near[2], "member", ""],
    ]
    planted["possible_duplicate_registration"] = f"REG-2611-03 looks like {near[0]} {near[1]}"
    planted["same_name_two_people"] = f"{members[4][0]} and FC-00059 are both {members[4][1]}"

    paths = {
        "current": _write(folder / CYCLE / "current_roster.csv", FIELDS, current),
        "prior": _write(folder / CYCLE / "prior_approvals.csv", FIELDS + ["approved_on"], prior),
        "registrations": _write(folder / CYCLE / "new_registrations.csv",
                                ["registration_ref", "display_name", "space_code", "requested_role", "member_id"],
                                registrations),
    }
    return {"paths": paths, "planted": planted}


def late_registration(folder: Path) -> None:
    path = folder / CYCLE / "new_registrations.csv"
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerow(["REG-2611-04", "Esme Saltmarrow", "AY", "member", "FC-00062"])
