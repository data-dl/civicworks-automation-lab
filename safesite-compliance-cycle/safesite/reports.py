"""The two Word reports, the QA pack, and the approval that turns drafts into finals.

Working drafts, QA material and approved finals live in three separate folders. A final is written
only when every assignment has an accepted return and a named role approves; an existing final is
never overwritten.
"""

from __future__ import annotations

import sqlite3
import stat
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .cycle import Workspace
from .runkit import SYNTHETIC_NOTICE, sha256_file, utc_now

VARIANTS = {
    "workshop": ("Workshop & Studio Facilities", "Quarterly safety observations"),
    "depot": ("Warehouse & Depot Facilities", "Quarterly safety observations and open actions"),
}
SEVERITY_LABEL = {"S1": "S1 note", "S2": "S2 minor", "S3": "S3 significant", "S4": "S4 urgent"}


@dataclass
class ReportResult:
    verdict: str
    drafts: list[str] = field(default_factory=list)
    finals: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def _table(doc: Document, header: list[str], rows: list[list]) -> None:
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Light Grid Accent 1"
    for cell, text in zip(table.rows[0].cells, header, strict=True):
        cell.text = text
        cell.paragraphs[0].runs[0].bold = True
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row, strict=True):
            cell.text = str(value)


def _banner(doc: Document, text: str, colour: RGBColor) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold, run.font.size, run.font.color.rgb = True, Pt(10), colour
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def build_report(con: sqlite3.Connection, quarter: str, variant: str, status: str, path: Path) -> Path:
    title, subtitle = VARIANTS[variant]
    rows = con.execute("SELECT a.*, f.name, c.role FROM assignment a JOIN facility f USING (facility_id) "
                       "JOIN coordinator c USING (coordinator_id) WHERE a.quarter = ? AND f.category = ? "
                       "ORDER BY a.facility_id", (quarter, variant)).fetchall()
    obs = con.execute("SELECT o.*, a.facility_id, f.name FROM observation o JOIN assignment a USING (assignment_id) "
                      "JOIN facility f USING (facility_id) WHERE a.quarter = ? AND f.category = ? "
                      "ORDER BY a.facility_id, o.observation_id", (quarter, variant)).fetchall()
    doc = Document()
    for section in doc.sections:
        section.header.paragraphs[0].text = f"{SYNTHETIC_NOTICE}   |   {status}"
    _banner(doc, f"{status} - {'not for circulation' if status != 'FINAL' else 'approved'}",
            RGBColor(0x9C, 0x57, 0x00) if status != "FINAL" else RGBColor(0x1E, 0x7A, 0x46))
    doc.add_heading(f"Meridian Facilities Consortium - {title}", level=0)
    doc.add_paragraph(f"{subtitle}, {quarter}. Fictional organisation; every facility, person and finding "
                      "is invented for demonstration.")

    doc.add_heading("Summary", level=1)
    counts = Counter(o["severity"] for o in obs)
    open_actions = sum(1 for o in obs if o["action_state"] != "closed")
    returned = sum(1 for r in rows if r["state"].startswith("accepted"))
    doc.add_paragraph(f"{returned} of {len(rows)} facilities returned accepted observations; "
                      f"{len(obs)} observations in total, {counts['S3'] + counts['S4']} significant or urgent, "
                      f"{open_actions} actions still open.")
    _table(doc, ["Severity", "Observations"], [[SEVERITY_LABEL[s], counts.get(s, 0)] for s in SEVERITY_LABEL])

    doc.add_heading("Facilities", level=1)
    _table(doc, ["Facility", "Coordinator", "Return", "Observations", "S3+S4", "Open actions"],
           [[r["name"], r["role"], r["state"] + (f" ({r['submitted_on']})" if r["submitted_on"] else ""),
             sum(1 for o in obs if o["facility_id"] == r["facility_id"]),
             sum(1 for o in obs if o["facility_id"] == r["facility_id"] and o["severity"] in ("S3", "S4")),
             sum(1 for o in obs if o["facility_id"] == r["facility_id"] and o["action_state"] != "closed")]
            for r in rows])

    if variant == "workshop":
        doc.add_heading("Significant and urgent observations", level=1)
        serious = [o for o in obs if o["severity"] in ("S3", "S4")]
        _table(doc, ["Facility", "Area", "Severity", "Finding", "Action", "Evidence"],
               [[o["name"], o["area"], SEVERITY_LABEL[o["severity"]], o["description"], o["action_state"],
                 o["evidence_ref"]] for o in serious])
    else:
        doc.add_heading("Open actions by area", level=1)
        by_area = Counter(o["area"] for o in obs if o["action_state"] != "closed")
        _table(doc, ["Area", "Open actions"], [[a, n] for a, n in sorted(by_area.items())])
        doc.add_heading("Loading and vehicle areas", level=2)
        vehicle = [o for o in obs if o["area"] in ("loading bay", "forklift lane", "yard gate")]
        _table(doc, ["Facility", "Area", "Severity", "Finding", "Action"],
               [[o["name"], o["area"], SEVERITY_LABEL[o["severity"]], o["description"], o["action_state"]]
                for o in vehicle])

    doc.add_heading("Data quality notes", level=1)
    notes = [f"{r['name']}: {r['state']}" + (f" - {r['note']}" if r["note"] else "")
             for r in rows if not r["state"].startswith("accepted") or r["state"] == "accepted-late"]
    for line in notes or ["Every return was accepted on time."]:
        doc.add_paragraph(line, style="List Bullet")
    doc.core_properties.author = "CivicWorks demo"
    doc.core_properties.title = f"{title} {quarter}"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def produce(ws: Workspace, quarter: str, approve_as: str | None = None) -> ReportResult:
    con = ws.open()
    try:
        states = con.execute("SELECT facility_id, state FROM assignment WHERE quarter = ?", (quarter,)).fetchall()
        blockers = [f"{s['facility_id']} is {s['state']}" for s in states if not s["state"].startswith("accepted")]
        existing = con.execute("SELECT variant FROM report_final WHERE quarter = ?", (quarter,)).fetchall()
        result = ReportResult("DRAFT", blockers=blockers)
        status = "DRAFT - INCOMPLETE" if blockers else "DRAFT"
        for variant in VARIANTS:
            path = build_report(con, quarter, variant, status, ws.working / quarter / f"{variant}_{quarter}_draft.docx")
            result.drafts.append(path.name)
        qa = ws.qa / quarter / f"QA_pack_{quarter}.md"
        qa.parent.mkdir(parents=True, exist_ok=True)
        rows = con.execute("SELECT a.facility_id, a.state, a.submitted_on, a.file_name, a.file_sha256, a.note, "
                           "(SELECT COUNT(*) FROM reminder r WHERE r.assignment_id = a.assignment_id) AS reminders "
                           "FROM assignment a WHERE quarter = ? ORDER BY facility_id", (quarter,)).fetchall()
        qa.write_text(f"# QA pack {quarter}\n\n_{SYNTHETIC_NOTICE}_\n\n| facility | state | received | file | "
                      "sha256 | reminders | note |\n|---|---|---|---|---|---|---|\n"
                      + "".join(f"| {r['facility_id']} | {r['state']} | {r['submitted_on'] or ''} | "
                                f"{r['file_name'] or ''} | {(r['file_sha256'] or '')[:12]} | {r['reminders']} | "
                                f"{r['note']} |\n" for r in rows)
                      + f"\nBlocking final approval: {', '.join(blockers) or 'nothing'}\n", encoding="utf-8")
        if not approve_as:
            result.verdict = "DRAFT (incomplete)" if blockers else "DRAFT (ready for approval)"
            return result
        if existing:
            result.verdict = "ALREADY FINAL; nothing overwritten"
            return result
        if blockers:
            result.verdict = "BLOCKED"
            return result
        for variant in VARIANTS:
            final = ws.final / quarter / f"{variant}_{quarter}_FINAL.docx"
            if final.exists():
                result.verdict = "ALREADY FINAL; nothing overwritten"
                return result
            build_report(con, quarter, variant, "FINAL", final)
            final.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            con.execute("INSERT INTO report_final VALUES (?, ?, ?, ?, ?, ?)",
                        (quarter, variant, final.name, sha256_file(final), approve_as, utc_now()))
            result.finals.append(final.name)
        con.commit()
        result.verdict = f"FINAL (approved by {approve_as})"
        return result
    finally:
        con.close()
