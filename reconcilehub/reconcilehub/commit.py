"""Commit: turn a fully reviewed reconciliation into an approved snapshot, an import workbook and a
change report. Blocked while any case is held. Re-running with the same inputs and decisions produces
the same snapshot hash and writes nothing new; different inputs after approval need --supersede and a
reason, and become a new version beside the old one."""

from __future__ import annotations

from dataclasses import dataclass, field

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .reconcile import Recon, Workspace, reconcile, roster_bytes, roster_sha
from .runkit import SYNTHETIC_NOTICE, Outbox, atomic_write_bytes, guard, utc_now

ACTION_FILL = {"ADD": "E2F0D9", "REMOVE": "F8CBAD", "CHANGE ROLE": "FFF2CC", "RENAME ID": "DDEBF7", "FIX ID": "DDEBF7"}


@dataclass
class CommitResult:
    verdict: str
    version: int | None = None
    files: list[str] = field(default_factory=list)
    drafts: list[str] = field(default_factory=list)


def _workbook(path, r: Recon, version: int) -> None:
    wb = Workbook()
    about = wb.active
    about.title = "About"
    for row in [["Foundry Commons access import", ""], ["Cycle", r.cycle], ["Version", f"v{version}"],
                ["Notice", SYNTHETIC_NOTICE],
                ["How to use", "Load the Import tab into the access system; Action says what each row does."]]:
        about.append(row)
    about["A1"].font = Font(bold=True, size=13)
    imp = wb.create_sheet("Import")
    imp.append(["Action", "Member ID", "Name", "Space", "Role", "Reason"])
    for cell in imp[1]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F4F4F")
    for a in sorted(r.actions, key=lambda a: (a["action"], a["member_id"])):
        imp.append([a["action"], a["member_id"], a["name"], a["space"], a["role"], a["reason"]])
        imp.cell(row=imp.max_row, column=1).fill = PatternFill("solid", fgColor=ACTION_FILL[a["action"]])
    exc = wb.create_sheet("Reviewed cases")
    exc.append(["Case", "Kind", "Confidence", "Disposition", "Detail"])
    for c in r.cases:
        exc.append([c.case_id, c.kind, c.confidence, c.disposition, c.detail])
    roster = wb.create_sheet("Approved roster")
    roster.append(["Member ID", "Name", "Space", "Role"])
    for k, v in sorted(r.approved.items()):
        roster.append([k, v["name"], v["space"], v["role"]])
    for ws_, widths in ((imp, [13, 12, 24, 7, 9, 60]), (exc, [44, 20, 11, 16, 90]), (roster, [12, 24, 7, 9]),
                        (about, [12, 80])):
        for i, w in enumerate(widths):
            ws_.column_dimensions[chr(65 + i)].width = w
    wb.save(path)


def _report(r: Recon, version: int, approver: str, sha: str, reason: str) -> str:
    counts = {k: sum(1 for a in r.actions if a["action"] == k) for k in ACTION_FILL}
    lines = [f"# Access change report {r.cycle} (v{version})", "", f"_{SYNTHETIC_NOTICE}_", "",
             f"- Approved by: {approver}", f"- Approved roster: {len(r.approved)} members, sha256 `{sha[:16]}`",
             f"- Unchanged: {r.unchanged}; ids normalised on the way in: {r.normalised_ids}"]
    if reason:
        lines.append(f"- Supersedes the previous version because: {reason}")
    lines += ["", "| action | count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in counts.items() if v]
    lines += ["", "## Changes", ""] + [f"- **{a['action']}** {a['member_id']} {a['name']} ({a['space']}, "
                                       f"{a['role']}): {a['reason']}" for a in r.actions]
    lines += ["", "## Reviewed cases", ""] + [f"- `{c.case_id}` -> **{c.disposition}** ({c.confidence:.0%}): "
                                              f"{c.detail}" for c in r.cases]
    lines += ["", "## Notes", ""] + [f"- {n}" for n in r.notes]
    return "\n".join(lines) + "\n"


def commit(ws: Workspace, cycle: str, approver: str, supersede: str | None = None) -> CommitResult:
    r = reconcile(ws, cycle)
    if r.held and guard("review-before-commit"):
        outbox = Outbox(ws.outbox / cycle)
        path = outbox.draft(f"{cycle}-held-cases", ["space.admins@example.org"],
                            f"{len(r.held)} roster cases need a decision before the {cycle} import",
                            "These could not be decided automatically:\n\n"
                            + "\n".join(f"  - {c.case_id}: {c.detail}" for c in r.held)
                            + "\n\nRecord same-person / different-person / exclude in the decisions file.\n")
        return CommitResult(f"BLOCKED: {len(r.held)} case(s) held for review", drafts=[path.name])
    sha = roster_sha(r.approved)
    con = ws.open()
    latest = con.execute("SELECT * FROM reconciliation_release WHERE cycle = ? ORDER BY version DESC LIMIT 1",
                         (cycle,)).fetchone()
    if latest and latest["sha256"] == sha:
        con.close()
        return CommitResult(f"NOTHING NEW: identical to v{latest['version']} (sha256 {sha[:12]})", latest["version"])
    if latest and not supersede:
        con.close()
        return CommitResult(f"REFUSED: v{latest['version']} is approved and the result now differs; rerun with "
                            "--supersede REASON to approve a new version", latest["version"])
    version = (latest["version"] + 1) if latest else 1
    folder = ws.snapshots / cycle / f"v{version}"
    folder.mkdir(parents=True, exist_ok=False)
    roster_path = atomic_write_bytes(folder / "approved_roster.csv", roster_bytes(r.approved))
    export = ws.exports / cycle
    export.mkdir(parents=True, exist_ok=True)
    workbook = export / f"Access_import_{cycle}_v{version}.xlsx"
    _workbook(workbook, r, version)
    report = export / f"Change_report_{cycle}_v{version}.md"
    report.write_text(_report(r, version, approver, sha, supersede or ""), encoding="utf-8")
    con.execute("INSERT INTO reconciliation_release (cycle, version, approved_by, sha256, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", (cycle, version, approver, sha, supersede or "", utc_now()))
    con.commit()
    con.close()
    return CommitResult(f"APPROVED v{version} (sha256 {sha[:12]})", version,
                        [roster_path.name, workbook.name, report.name])
