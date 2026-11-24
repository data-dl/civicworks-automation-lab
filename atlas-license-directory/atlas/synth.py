"""Four independent source catalogs for the fictional Four Districts Craft Coalition.

members.csv, studios.csv, endorsements.csv and listings.csv arrive from separate systems, so they
disagree in the usual ways: crafts spelled differently, phone numbers in different formats, a
listing row sent twice. `plant_problems` adds one example of every problem the QA rules exist for;
`repair_sources` is what a directory editor would fix; `next_period` is the following month's data.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DISTRICTS = [("CR", "Cinderreach"), ("LM", "Larkmoor"), ("SW", "Saltwick"), ("TV", "Thornvale")]
CRAFTS = [("CER", "Ceramics"), ("GLS", "Glassblowing"), ("WVG", "Weaving"), ("LTH", "Leatherwork"),
          ("SMT", "Smithing"), ("JNR", "Joinery"), ("PRT", "Printmaking"), ("BKB", "Bookbinding"),
          ("DYE", "Natural dyeing"), ("BSK", "Basketry"), ("JWL", "Jewellery"), ("TRN", "Wood turning")]
# how the sources actually spell the crafts; normalisation maps all of these to the code
SPELLINGS = {"CER": ["Ceramics", "ceramic", "CER"], "GLS": ["Glassblowing", "glass blowing"],
             "WVG": ["Weaving", "weaving"], "LTH": ["Leatherwork", "leather work"], "SMT": ["Smithing", "smithy"],
             "JNR": ["Joinery", "joinery"], "PRT": ["Printmaking", "print making"], "BKB": ["Bookbinding"],
             "DYE": ["Natural dyeing", "dyeing"], "BSK": ["Basketry", "basket weaving"],
             "JWL": ["Jewellery", "jewelry"], "TRN": ["Wood turning", "woodturning"]}
GIVEN = ["Ada", "Bram", "Cora", "Dace", "Elin", "Fitz", "Greer", "Hale", "Isla", "Joss", "Kestrel", "Lior",
         "Maren", "Nico", "Odile", "Perrin", "Quill", "Roan", "Sorrel", "Tamsin", "Ulric", "Vesna", "Wren", "Yael"]
FAMILY = ["Ashcombe", "Brackenridge", "Coldharbour", "Dewhollow", "Elderwick", "Fairmarsh", "Greythorn",
          "Hartsease", "Ironvale", "Juniperlow", "Kettlewell", "Lanternby", "Mistlecombe", "Nettlebridge",
          "Oakhollow", "Pennywhistle", "Quarrybrook", "Rookfield", "Saltmarch", "Thistlewood"]
STUDIO_WORDS = ["Kiln", "Loom", "Forge", "Bench", "Press", "Lathe", "Bindery", "Vat", "Yard", "Hall"]
PERIOD = "2026-11"
RELEASE_DATE = date(2026, 12, 1)   # the edition goes out on this day; endorsements must still be valid then


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _read(path: Path) -> tuple[list[str], list[list]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def generate(folder: Path, seed: int = 20261123, members: int = 150) -> dict:
    rng = random.Random(seed)
    names, member_rows = set(), []
    while len(member_rows) < members:
        name = f"{rng.choice(GIVEN)} {rng.choice(FAMILY)}"
        if name in names:
            continue
        names.add(name)
        digits = f"{rng.randrange(200, 999)}{rng.randrange(1000, 9999)}"
        phone = rng.choice([f"555-{digits[:3]}-{digits[3:]}", f"(555) {digits[:3]} {digits[3:]}", f"555.{digits}"])
        state = rng.choices(["active", "suspended", "retired"], weights=[88, 7, 5])[0]
        member_rows.append([f"M{len(member_rows) + 1:04d}", name, phone, state, rng.choice([0, 1, 1, 1])])
    studio_rows = []
    for i in range(1, 49):
        code, label = DISTRICTS[(i - 1) % 4]
        studio_rows.append([f"S{i:03d}", f"{label} {rng.choice(STUDIO_WORDS)} {i:02d}", code,
                            f"V-{code}-{rng.randrange(100, 999)}"])
    endorsement_rows, listing_rows = [], []
    for n, (mid, *_rest) in enumerate(member_rows, start=1):
        code = CRAFTS[n % len(CRAFTS)][0]
        start = date(2025, 1, 1) + timedelta(days=rng.randint(0, 500))
        end = start + timedelta(days=rng.choice([730, 1095]))
        if end <= RELEASE_DATE:
            end = RELEASE_DATE + timedelta(days=rng.randint(60, 600))
        endorsement_rows.append([f"E{n:04d}", mid, rng.choice(SPELLINGS[code]), start.isoformat(), end.isoformat()])
        studio = rng.choice(studio_rows)[0]
        opt_in = member_rows[n - 1][4]
        editions = ["member", "inspector"] + (["public"] if opt_in else [])
        for edition in editions:
            listing_rows.append([mid, studio, edition, 1])
    paths = {}
    for name, header, rows in (
            ("members", ["member_id", "name", "phone", "state", "public_opt_in"], member_rows),
            ("studios", ["studio_id", "studio_name", "district", "venue_token"], studio_rows),
            ("endorsements", ["endorsement_id", "member_id", "craft", "valid_from", "valid_to"], endorsement_rows),
            ("listings", ["member_id", "studio_id", "edition", "approved"], listing_rows)):
        path = folder / PERIOD / f"{name}.csv"
        _write(path, header, rows)
        paths[name] = path
    return {"members": len(member_rows), "studios": len(studio_rows), "endorsements": len(endorsement_rows),
            "listings": len(listing_rows), "seed": seed}


def plant_problems(folder: Path) -> dict:
    """One case of each problem the rule registry knows about; returns what was planted where."""
    base = folder / PERIOD
    h, members = _read(base / "members.csv")
    near = members[len(members) * 2 // 3]
    members.append(["M0042", "Joss Rookfield", "555-301-2240", "active", "1"])      # same id, different person
    members.append(["M0151", near[1][:-1], "555 410 7781", "active", "1"])           # a near-copy of a name
    _write(base / "members.csv", h, members)
    h, studios = _read(base / "studios.csv")
    studios[18][2] = "NM"                                                          # a district that does not exist
    studios[22][3] = ""                                                            # missing venue token
    _write(base / "studios.csv", h, studios)
    h, ends = _read(base / "endorsements.csv")
    ends[6][4] = "2026-10-31"                                                      # expires before the edition
    ends[11][4] = "2027-02-30"                                                     # not a real date
    ends[15][2] = "Glasblowing"                                                    # unmapped spelling
    ends.append(["E0151", "M0151", "Ceramics", "2026-01-05", "2028-01-05"])
    _write(base / "endorsements.csv", h, ends)
    h, listings = _read(base / "listings.csv")
    opted_out = next(m for m in members if m[4] == "0")
    listings.append([opted_out[0], listings[0][1], "public", "1"])                 # public, but did not opt in
    listings.append(list(listings[5]))                                             # the same row sent twice
    listings.append(["M0151", listings[0][1], "member", "1"])
    _write(base / "listings.csv", h, listings)
    return {"duplicate_member_id": "M0042", "near_duplicate_name": f"{near[0]} / M0151",
            "orphaned_studio": studios[18][0], "missing_venue_token": studios[22][0],
            "expired_endorsement": ends[6][1], "invalid_date": ends[11][0], "unknown_craft": ends[15][0],
            "contradictory_audience": opted_out[0], "repeated_listing_row": f"{listings[5][0]} {listings[5][2]}"}


def repair_sources(folder: Path) -> list[str]:
    """What the directory editor fixes after reading the QA report. Advisory items are left as they are."""
    base = folder / PERIOD
    fixes = []
    h, members = _read(base / "members.csv")
    seen, kept = set(), []
    for m in members:
        if m[0] in seen:
            fixes.append(f"removed second {m[0]} ({m[1]}): it belongs to another person and needs its own id")
            continue
        seen.add(m[0])
        kept.append(m)
    _write(base / "members.csv", h, kept)
    h, studios = _read(base / "studios.csv")
    for s in studios:
        if s[2] == "NM":
            s[2] = "LM"
            fixes.append(f"{s[0]}: district NM corrected to LM")
    _write(base / "studios.csv", h, studios)
    h, ends = _read(base / "endorsements.csv")
    for e in ends:
        if e[4] == "2026-10-31":
            e[4] = "2028-10-31"
            fixes.append(f"{e[0]}: renewal recorded, valid to 2028-10-31")
        if e[4] == "2027-02-30":
            e[4] = "2027-02-28"
            fixes.append(f"{e[0]}: 2027-02-30 corrected to 2027-02-28")
        if e[2] == "Glasblowing":
            e[2] = "Glassblowing"
            fixes.append(f"{e[0]}: craft spelling corrected")
    _write(base / "endorsements.csv", h, ends)
    h, listings = _read(base / "listings.csv")
    opted_out = {m[0] for m in kept if m[4] == "0"}
    before = len(listings)
    listings = [row for row in listings if not (row[2] == "public" and row[0] in opted_out)]
    if len(listings) < before:
        fixes.append(f"withdrew {before - len(listings)} public listing(s) for people who did not opt in")
    _write(base / "listings.csv", h, listings)
    return fixes


def next_period(folder: Path, period: str = "2026-12", seed: int = 7) -> dict:
    """The following month: copy the sources, add three new listings, withdraw two."""
    rng = random.Random(seed)
    src, dst = folder / PERIOD, folder / period
    for name in ("members", "studios", "endorsements"):
        h, rows = _read(src / f"{name}.csv")
        _write(dst / f"{name}.csv", h, rows)
    h, listings = _read(src / "listings.csv")
    withdrawn = [listings.pop(rng.randrange(len(listings))) for _ in range(2)]
    _, members = _read(src / "members.csv")
    _, studios = _read(src / "studios.csv")
    listed = {(row[0], row[2]) for row in listings}
    added = []
    for m in members:
        if m[3] == "active" and (m[0], "member") in listed and (m[0], "inspector") in listed and len(added) < 3:
            studio = rng.choice(studios)[0]
            if (m[0], studio) not in {(r[0], r[1]) for r in listings}:
                listings.append([m[0], studio, "member", "1"])
                added.append(f"{m[0]} at {studio}")
    _write(dst / "listings.csv", h, listings)
    return {"withdrawn": [f"{w[0]} {w[2]}" for w in withdrawn], "added": added}
