"""The fictional Harbor Arts Network and its quarterly submission files, from a fixed seed.

Four invented regions, two venues of each service tier per region. Each venue sends one CSV per
quarter. Defect functions produce exactly the problems the pipeline must catch: a venue that never
reports, a total that does not add up, a second version of a file, a file for the wrong quarter, and
a large swing that needs commentary.
"""

from __future__ import annotations

import csv
import io
import random
import sqlite3
from pathlib import Path

REGIONS = [("NF", "Northfield"), ("EM", "Eastmere"), ("SB", "Southbank"), ("WV", "Westvale")]
STUDIO_NAMES = ["Kiln House", "Print Loft", "Loom Rooms", "Pixel Shed"]
OUTREACH_NAMES = ["Mobile Press", "Clay Van", "Pop-up Looms", "Story Bus"]
CATEGORIES = ["ceramics", "printmaking", "textiles", "digital media"]
SINGLE_METRICS = ["sessions_delivered", "first_time_visitors", "complaints", "improvements_logged",
                  "incidents_minor", "incidents_reportable"]
QUARTERS = ["2026Q2", "2026Q3"]
HEADER = ["quarter", "venue_id", "tier", "metric_code", "category", "amount"]


def build_network(con: sqlite3.Connection, seed: int = 20261123) -> list[tuple[str, str, str, str]]:
    rng = random.Random(seed)
    con.executemany("INSERT INTO region VALUES (?, ?)", REGIONS)
    venues = []
    for code, label in REGIONS:
        studios = rng.sample(STUDIO_NAMES, 2)
        outreach = rng.sample(OUTREACH_NAMES, 2)
        for i, name in enumerate(studios + outreach, start=1):
            tier = "studio" if i <= 2 else "outreach"
            venues.append((f"HV-{code}{i:02d}", f"{label} {name}", code, tier))
    con.executemany("INSERT INTO venue (venue_id, name, region_code, tier) VALUES (?, ?, ?, ?)", venues)
    for q in QUARTERS:
        con.execute("INSERT INTO quarter VALUES (?, ?, ?)", (q, int(q[:4]), int(q[-1])))
    con.commit()
    return venues


def venue_figures(rng: random.Random, tier: str, boost: float = 1.0) -> dict:
    scale = 1.0 if tier == "studio" else 0.55
    by_category = {c: int(rng.randint(120, 480) * scale * boost) for c in CATEGORIES}
    total = sum(by_category.values())
    return {
        "attendance": by_category,
        "attendance_total": total,
        "sessions_delivered": max(8, total // rng.randint(18, 30)),
        "first_time_visitors": int(total * rng.uniform(0.18, 0.42)),
        "complaints": rng.randint(0, 6),
        "improvements_logged": rng.randint(0, 5),
        "incidents_minor": rng.randint(0, 4),
        "incidents_reportable": rng.choices([0, 1, 2], weights=[80, 15, 5])[0],
    }


def submission_csv(quarter: str, venue_id: str, tier: str, figures: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(HEADER)
    for category, amount in figures["attendance"].items():
        w.writerow([quarter, venue_id, tier, "attendance", category, amount])
    w.writerow([quarter, venue_id, tier, "attendance_total", "", figures["attendance_total"]])
    for metric in SINGLE_METRICS:
        w.writerow([quarter, venue_id, tier, metric, "", figures[metric]])
    return out.getvalue()


def write_quarter(inbox: Path, venues, quarter: str, seed: int, defects: bool = False) -> dict:
    """One file per venue. With `defects`, plant the five problems and report where they are."""
    rng = random.Random(f"{seed}-{quarter}")
    folder = inbox / quarter
    folder.mkdir(parents=True, exist_ok=True)
    planted = {}
    for venue_id, _, region, tier in venues:
        boost = 1.8 if (defects and region == "WV" and tier == "outreach") else 1.0
        figures = venue_figures(rng, tier, boost)
        text = submission_csv(quarter, venue_id, tier, figures)
        if defects and venue_id == "HV-EM03":
            planted["missing_contributor"] = venue_id
            continue
        if defects and venue_id == "HV-SB02":
            planted["wrong_period"] = venue_id
            text = text.replace(quarter, "2026Q2")
        if defects and venue_id == "HV-NF01":
            planted["totals_mismatch"] = venue_id
            text = text.replace(f"attendance_total,,{figures['attendance_total']}",
                                f"attendance_total,,{figures['attendance_total'] + 37}")
        (folder / f"{venue_id}_v1.csv").write_text(text, encoding="utf-8", newline="")
        if defects and venue_id == "HV-WV02":
            planted["duplicate_submission"] = venue_id
            revised = venue_figures(random.Random(f"{seed}-{venue_id}-v2"), tier, boost)
            (folder / f"{venue_id}_v2.csv").write_text(submission_csv(quarter, venue_id, tier, revised),
                                                       encoding="utf-8", newline="")
        if defects and region == "WV" and tier == "outreach":
            planted.setdefault("large_swing", "Westvale outreach")
    return planted


def write_late_files(inbox: Path, venues, quarter: str, seed: int) -> list[str]:
    """What the venues send after the reminder: the missing file and corrected versions of the bad ones."""
    rng = random.Random(f"{seed}-{quarter}-late")
    folder = inbox / quarter
    written = []
    tiers = {v[0]: v[3] for v in venues}
    for venue_id, version in (("HV-EM03", 1), ("HV-SB02", 2), ("HV-NF01", 2)):
        text = submission_csv(quarter, venue_id, tiers[venue_id], venue_figures(rng, tiers[venue_id]))
        name = f"{venue_id}_v{version}.csv"
        (folder / name).write_text(text, encoding="utf-8", newline="")
        written.append(name)
    return written
