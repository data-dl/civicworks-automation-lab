"""One quarter, end to end: discover -> ingest -> validate -> compare -> build -> draft -> approve.

The quarter's submissions are re-derived from the inbox on every run until the quarter is approved.
After approval the figures are frozen: the approved workbooks live in their own folder, are never
overwritten, and a later run only checks whether the inbox still matches what was approved.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sqlite3
import stat
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from .db import connect, migrate
from .runkit import Manifest, Outbox, sha256_file, unique_dir, utc_now, write_json
from .workbooks import build_incident_workbook, build_tier_workbook

PROJECT = "regional-programs-analytics"
SWING = 0.40
FILE_NAME = re.compile(r"^(?P<venue>HV-[A-Z]{2}\d{2})_v(?P<version>\d+)\.csv$")
RECIPIENTS = [
    ("Program director", "director@example.org", "all three workbooks"),
    ("Board liaison", "board.liaison@example.org", "the Summary tabs only"),
    ("Regional leads", "regional.leads@example.org", "their region's rows in By Venue"),
]


@dataclass
class Finding:
    rule: str
    severity: str  # blocking | advisory
    detail: str


@dataclass
class QuarterResult:
    quarter: str
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    accepted: int = 0
    expected: int = 0
    outputs: list[str] = field(default_factory=list)
    approved_folder: str | None = None
    run_dir: str = ""

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocking"]


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    db = property(lambda self: self.root / "regional.sqlite")
    inbox = property(lambda self: self.root / "inbox")
    drafts = property(lambda self: self.root / "drafts")
    approved = property(lambda self: self.root / "approved")
    outbox = property(lambda self: self.root / "outbox")
    runs = property(lambda self: self.root / "runs")

    def open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = connect(self.db)
        migrate(con)
        return con


def prior_quarter(quarter: str) -> str:
    year, number = int(quarter[:4]), int(quarter[-1])
    return f"{year - 1}Q4" if number == 1 else f"{year}Q{number - 1}"


def latest_release(con: sqlite3.Connection, quarter: str):
    return con.execute("SELECT * FROM report_release WHERE quarter_id = ? ORDER BY version DESC LIMIT 1",
                       (quarter,)).fetchone()


def _parse(path: Path) -> tuple[str | None, list[dict], str | None]:
    try:
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return None, [], f"unreadable: {exc}"
    if not rows or set(rows[0]) != {"quarter", "venue_id", "tier", "metric_code", "category", "amount"}:
        return None, [], "unexpected columns"
    quarters = {r["quarter"] for r in rows}
    try:
        for r in rows:
            r["amount"] = int(r["amount"])
            if r["amount"] < 0:
                return None, [], f"negative amount for {r['metric_code']}"
    except ValueError:
        return None, [], "non-numeric amount"
    return (quarters.pop() if len(quarters) == 1 else "mixed"), rows, None


def figures_by_venue(con: sqlite3.Connection, quarter: str) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"attendance_by_category": {}})
    for r in con.execute("SELECT s.venue_id, m.metric_code, m.category, m.amount FROM measure m "
                         "JOIN submission s ON s.submission_id = m.submission_id "
                         "WHERE s.quarter_id = ? AND s.status = 'accepted'", (quarter,)):
        if r["metric_code"] == "attendance":
            out[r["venue_id"]]["attendance_by_category"][r["category"]] = r["amount"]
        else:
            out[r["venue_id"]][r["metric_code"]] = r["amount"]
    for v in out.values():
        v["attendance"] = sum(v["attendance_by_category"].values())
    return dict(out)


def run_quarter(ws: Workspace, quarter: str, *, approve_as: str | None = None, new_version: bool = False,
                seed: int | None = None) -> QuarterResult:
    con = ws.open()
    result = QuarterResult(quarter, "incomplete")
    run_dir = unique_dir(ws.runs, f"{quarter}-{utc_now()[:19].replace(':', '').replace('-', '')}")
    result.run_dir = str(run_dir)
    manifest = Manifest(PROJECT, run_dir.name, __version__, "1", seed, mode="approve" if approve_as else "review")
    finding = result.findings.append
    released = latest_release(con, quarter)
    frozen = released is not None and not new_version

    # -- discover ---------------------------------------------------------------------------------
    stage = manifest.begin("discover")
    files = sorted((ws.inbox / quarter).glob("*.csv")) if (ws.inbox / quarter).exists() else []
    for f in files:
        manifest.add_input(f, ws.root)
    manifest.end(stage, files=len(files))

    venues = {r["venue_id"]: dict(r) for r in con.execute("SELECT * FROM venue WHERE active = 1")}
    result.expected = len(venues)

    # -- ingest -----------------------------------------------------------------------------------
    stage = manifest.begin("ingest")
    if frozen:
        approved_inputs = json.loads(released["inputs_json"])
        changed = sorted(n for n, h in approved_inputs.items()
                         if not (ws.inbox / quarter / n).exists() or sha256_file(ws.inbox / quarter / n) != h)
        if changed:
            finding(Finding("changed_since_approval", "blocking",
                            f"{len(changed)} approved input(s) changed or vanished since v{released['version']} "
                            f"was approved: {', '.join(changed[:4])}"))
        manifest.end(stage, "skipped", reason=f"quarter approved as v{released['version']}; figures frozen")
    else:
        con.execute("DELETE FROM measure WHERE submission_id IN (SELECT submission_id FROM submission "
                    "WHERE quarter_id = ?)", (quarter,))
        con.execute("DELETE FROM submission WHERE quarter_id = ?", (quarter,))
        candidates: dict[str, list[tuple[int, Path, list[dict]]]] = defaultdict(list)
        for f in files:
            match = FILE_NAME.match(f.name)
            sha = sha256_file(f)
            if not match or match["venue"] not in venues:
                finding(Finding("unknown_file", "blocking", f"{f.name}: not a known venue's submission"))
                continue
            venue_id, version = match["venue"], int(match["version"])
            file_quarter, rows, error = _parse(f)
            reason = error or (None if file_quarter == quarter else f"file is for {file_quarter}, not {quarter}")
            if reason:
                rule = "wrong_period" if error is None else "unreadable_file"
                finding(Finding(rule, "blocking" if rule == "unreadable_file" else "advisory", f"{f.name}: {reason}"))
                con.execute("INSERT INTO submission (venue_id, quarter_id, version, file_name, file_sha256, status, "
                            "reason) VALUES (?, ?, ?, ?, ?, 'rejected', ?)", (venue_id, quarter, version, f.name,
                                                                               sha, reason))
                continue
            candidates[venue_id].append((version, f, rows))
        for venue_id, versions in sorted(candidates.items()):
            versions.sort(key=lambda v: v[0])
            *older, (version, f, rows) = versions
            for old_version, old_file, _ in older:
                con.execute("INSERT INTO submission (venue_id, quarter_id, version, file_name, file_sha256, status, "
                            "reason) VALUES (?, ?, ?, ?, ?, 'superseded', ?)",
                            (venue_id, quarter, old_version, old_file.name, sha256_file(old_file),
                             f"replaced by v{version}"))
            if older:
                finding(Finding("duplicate_submission", "advisory",
                                f"{venue_id}: {len(versions)} versions received; v{version} used, "
                                f"{', '.join('v' + str(o[0]) for o in older)} kept as superseded"))
            cur = con.execute("INSERT INTO submission (venue_id, quarter_id, version, file_name, file_sha256, status) "
                              "VALUES (?, ?, ?, ?, ?, 'accepted')", (venue_id, quarter, version, f.name,
                                                                      sha256_file(f)))
            con.executemany("INSERT INTO measure (submission_id, metric_code, category, amount) VALUES (?, ?, ?, ?)",
                            [(cur.lastrowid, r["metric_code"], r["category"], r["amount"]) for r in rows])
        con.commit()
        manifest.end(stage, accepted=len(candidates))

    # -- validate ---------------------------------------------------------------------------------
    stage = manifest.begin("validate")
    current = figures_by_venue(con, quarter)
    result.accepted = len(current)
    for venue_id in sorted(set(venues) - set(current)):
        finding(Finding("missing_contributor", "blocking", f"{venue_id} ({venues[venue_id]['name']}) has not "
                                                            "submitted a usable file"))
    for venue_id, fig in sorted(current.items()):
        if fig.get("attendance_total") != fig["attendance"]:
            finding(Finding("totals_reconcile", "blocking",
                            f"{venue_id}: attendance_total {fig.get('attendance_total')} but categories sum to "
                            f"{fig['attendance']}"))
    prior = prior_quarter(quarter)
    prior_release = latest_release(con, prior)
    if prior_release is None:
        finding(Finding("prior_quarter", "advisory", f"{prior} is not approved; comparison is provisional"))
    else:
        inputs = json.loads(prior_release["inputs_json"])
        stale = [n for n, h in inputs.items()
                 if not (ws.inbox / prior / n).exists() or sha256_file(ws.inbox / prior / n) != h]
        if stale:
            finding(Finding("stale_prior_quarter", "blocking",
                            f"{prior} inputs changed since that quarter was approved ({', '.join(stale[:3])}); "
                            "re-approve it or restore the files before comparing"))
    manifest.end(stage, "blocked" if result.blocking else "ok", findings=[asdict(f) for f in result.findings])

    # -- compare ----------------------------------------------------------------------------------
    stage = manifest.begin("compare")
    previous = figures_by_venue(con, prior) if prior_release else {}
    comparison = []
    regions = {r["region_code"]: r["label"] for r in con.execute("SELECT * FROM region ORDER BY region_code")}
    for tier in ("studio", "outreach"):
        for code, label in regions.items():
            ids = [v for v, d in venues.items() if d["region_code"] == code and d["tier"] == tier]
            # like for like: a venue that has not reported yet is a missing contributor, not a drop
            both = [v for v in ids if v in current and v in previous]
            now = sum(current[v]["attendance"] for v in both)
            before = sum(previous[v]["attendance"] for v in both)
            change = (now - before) / before if before else None
            flag = change is not None and abs(change) > SWING
            gap = len(ids) - len(both)
            comparison.append({"tier": tier, "region": label, "prior": before, "current": now, "change": change,
                               "flag": "needs commentary" if flag else (f"{gap} venue(s) not compared" if gap else "")})
            if flag:
                finding(Finding("large_swing", "advisory", f"{label} {tier}: attendance {change:+.0%} vs {prior}; "
                                                           "add commentary to the review pack"))
    manifest.end(stage, rows=len(comparison))

    # -- build ------------------------------------------------------------------------------------
    stage = manifest.begin("build")
    status = "APPROVED" if approve_as and not result.blocking and not frozen else "DRAFT"
    draft_dir = ws.drafts / quarter
    draft_dir.mkdir(parents=True, exist_ok=True)
    context = {"quarter": quarter, "prior": prior, "status": status, "venues": venues, "regions": regions,
               "current": current, "comparison": comparison, "findings": [asdict(f) for f in result.findings]}
    built = [build_tier_workbook(draft_dir / f"Studio_{quarter}.xlsx", "studio", context),
             build_tier_workbook(draft_dir / f"Outreach_{quarter}.xlsx", "outreach", context),
             build_incident_workbook(draft_dir / f"Incidents_{quarter}.xlsx", context)]
    checklist = draft_dir / f"Review_pack_{quarter}.md"
    checklist.write_text(_review_pack(context, result), encoding="utf-8")
    for path in [*built, checklist]:
        manifest.add_output(path, ws.root)
        result.outputs.append(path.name)
    manifest.end(stage, status=status)

    # -- draft distribution -----------------------------------------------------------------------
    stage = manifest.begin("draft_distribution")
    outbox = Outbox(ws.outbox / quarter)
    for role, address, what in RECIPIENTS:
        outbox.draft(f"{quarter}-{role.lower().replace(' ', '-')}", [address],
                     f"Harbor Arts Network quarterly pack {quarter} ({status.lower()})",
                     f"Hello {role},\n\nThe {quarter} pack is {status.lower()}. You receive {what}.\n"
                     f"Open findings: {len(result.blocking)} blocking, "
                     f"{len(result.findings) - len(result.blocking)} advisory.\n")
    manifest.end(stage, "dry-run", drafts=len(RECIPIENTS), note="drafts only; nothing is sent")

    # -- approve ----------------------------------------------------------------------------------
    stage = manifest.begin("approve")
    if not approve_as:
        result.verdict = "BLOCKED" if result.blocking else "READY FOR APPROVAL"
        manifest.end(stage, "skipped")
    elif frozen:
        result.verdict = f"ALREADY APPROVED (v{released['version']}); nothing replaced"
        manifest.end(stage, "blocked", reason="use --new-version to approve a revision")
    elif result.blocking:
        result.verdict = "BLOCKED"
        manifest.end(stage, "blocked", blocking=len(result.blocking))
    else:
        version = (released["version"] + 1) if released else 1
        target = ws.approved / quarter / f"v{version}"
        target.mkdir(parents=True, exist_ok=False)
        outputs = {}
        for path in built:
            dest = target / path.name
            shutil.copy2(path, dest)
            dest.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            outputs[path.name] = sha256_file(dest)
            manifest.add_output(dest, ws.root)
        inputs = {r["file_name"]: r["file_sha256"] for r in con.execute(
            "SELECT file_name, file_sha256 FROM submission WHERE quarter_id = ? AND status = 'accepted'", (quarter,))}
        con.execute("INSERT INTO report_release (quarter_id, version, approved_by, approved_at, inputs_json, "
                    "outputs_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (quarter, version, approve_as, utc_now(), json.dumps(inputs), json.dumps(outputs)))
        con.commit()
        manifest.approval_id = f"{quarter}-v{version}"
        result.verdict = f"APPROVED v{version}"
        result.approved_folder = str(target)
        manifest.end(stage, approved_by=approve_as, folder=target.relative_to(ws.root).as_posix())

    manifest.verdict = result.verdict
    write_json(run_dir / "findings.json", [asdict(f) for f in result.findings])
    manifest.write(run_dir / "manifest.json")
    con.close()
    return result


def _review_pack(ctx: dict, result: QuarterResult) -> str:
    lines = [f"# Review pack - Harbor Arts Network {ctx['quarter']} ({ctx['status']})", "",
             "_DEMO / SYNTHETIC: every venue, region and number is invented._", "",
             f"- Submissions used: {result.accepted} of {result.expected}",
             f"- Blocking findings: {len(result.blocking)}",
             f"- Advisory findings: {len(result.findings) - len(result.blocking)}", "", "## Checklist", ""]
    checks = [("Every venue has a usable submission",
               not any(f.rule == "missing_contributor" for f in result.findings)),
              ("Category attendance adds up to the reported total",
               not any(f.rule == "totals_reconcile" for f in result.findings)),
              ("No file for the wrong quarter was used", True),
              ("Prior quarter is approved and unchanged",
               not any(f.rule in ("prior_quarter", "stale_prior_quarter") for f in result.findings)),
              ("Large swings have commentary", not any(f.rule == "large_swing" for f in result.findings))]
    lines += [f"- [{'x' if ok else ' '}] {text}" for text, ok in checks]
    lines += ["", "## Findings", ""] + [f"- **{f.severity}** `{f.rule}`: {f.detail}" for f in result.findings]
    swings = [c for c in ctx["comparison"] if c["flag"] == "needs commentary"]
    if swings:
        lines += ["", "## Variance commentary to write", ""]
        lines += [f"- {c['region']} {c['tier']}: {c['prior']} -> {c['current']} ({c['change']:+.0%}). "
                  "Explain the change before approval." for c in swings]
    return "\n".join(lines) + "\n"
