"""Regional Programs Analytics: the quarterly cycle and each problem the specification names."""

from __future__ import annotations

import json
import sqlite3
from email import message_from_bytes

import pytest
from openpyxl import load_workbook

from regional import synth
from regional.cli import init, main
from regional.pipeline import Workspace, run_quarter


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "ws")
    info = init(workspace, seed=5)
    workspace.info = info
    return workspace


def rules(result, severity=None):
    return {f.rule for f in result.findings if severity is None or f.severity == severity}


def test_same_seed_same_submission_files(tmp_path):
    texts = []
    for name in ("a", "b"):
        w = Workspace(tmp_path / name)
        init(w, seed=9)
        texts.append({p.name: p.read_bytes() for p in (w.inbox / "2026Q3").glob("*.csv")})
    assert texts[0] == texts[1] and len(texts[0]) == 16


def test_clean_quarter_is_ready_and_approval_freezes_it(ws):
    r = run_quarter(ws, "2026Q2")
    assert r.verdict == "READY FOR APPROVAL" and r.accepted == 16 and not r.blocking
    r = run_quarter(ws, "2026Q2", approve_as="director")
    assert r.verdict == "APPROVED v1"
    approved = ws.approved / "2026Q2" / "v1"
    assert sorted(p.name for p in approved.iterdir()) == ["Incidents_2026Q2.xlsx", "Outreach_2026Q2.xlsx",
                                                          "Studio_2026Q2.xlsx"]
    again = run_quarter(ws, "2026Q2", approve_as="director")
    assert again.verdict.startswith("ALREADY APPROVED") and not (ws.approved / "2026Q2" / "v2").exists()


def test_each_planted_problem_is_found(ws):
    run_quarter(ws, "2026Q2", approve_as="director")
    r = run_quarter(ws, "2026Q3", approve_as="director")
    assert r.verdict == "BLOCKED" and not (ws.approved / "2026Q3").exists()
    details = " ".join(f.detail for f in r.findings)
    assert {"missing_contributor", "totals_reconcile"} <= rules(r, "blocking")
    assert "HV-EM03" in details and "HV-NF01" in details
    assert any(f.rule == "wrong_period" and "HV-SB02_v1" in f.detail for f in r.findings)
    assert any(f.rule == "duplicate_submission" and "HV-WV02" in f.detail for f in r.findings)
    assert [f.detail.split(":")[0] for f in r.findings if f.rule == "large_swing"] == ["Westvale outreach"]


def test_only_one_accepted_submission_per_venue_and_quarter(ws):
    run_quarter(ws, "2026Q3")
    con = sqlite3.connect(ws.db)
    rows = con.execute("SELECT version, status FROM submission WHERE venue_id = 'HV-WV02' ORDER BY version").fetchall()
    assert rows == [(1, "superseded"), (2, "accepted")]
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO submission (venue_id, quarter_id, version, file_name, file_sha256, status) "
                    "VALUES ('HV-WV02', '2026Q3', 3, 'x', 'y', 'accepted')")
    con.close()


def test_late_files_clear_the_block_and_the_quarter_is_approved(ws):
    run_quarter(ws, "2026Q2", approve_as="director")
    run_quarter(ws, "2026Q3")
    synth.write_late_files(ws.inbox, ws.info["venues"], "2026Q3", seed=5)
    r = run_quarter(ws, "2026Q3", approve_as="director")
    assert r.verdict == "APPROVED v1" and r.accepted == 16


def test_stale_prior_quarter_blocks_the_comparison(ws):
    run_quarter(ws, "2026Q2", approve_as="director")
    approved_file = ws.inbox / "2026Q2" / "HV-NF02_v1.csv"
    approved_file.write_text(approved_file.read_text(encoding="utf-8").replace("2026Q2,HV-NF02,studio,complaints,,",
                                                                                 "2026Q2,HV-NF02,studio,complaints,,9"),
                             encoding="utf-8")
    r = run_quarter(ws, "2026Q3")
    assert "stale_prior_quarter" in rules(r, "blocking")
    frozen = run_quarter(ws, "2026Q2")
    assert "changed_since_approval" in rules(frozen, "blocking")


def test_unapproved_prior_quarter_makes_the_comparison_provisional(ws):
    r = run_quarter(ws, "2026Q3")
    assert any(f.rule == "prior_quarter" and f.severity == "advisory" for f in r.findings)


def test_workbooks_use_formulas_and_carry_the_status(ws):
    run_quarter(ws, "2026Q2", approve_as="director")
    wb = load_workbook(ws.approved / "2026Q2" / "v1" / "Studio_2026Q2.xlsx")
    assert wb.sheetnames == ["About", "Summary", "By Venue", "By Region", "Quarter Comparison", "QA Checks"]
    assert wb["About"]["B5"].value == "APPROVED" and "SYNTHETIC" in wb["About"]["B6"].value
    assert wb["Summary"]["B4"].value.startswith("=SUM('By Venue'!E2:E")
    assert wb["By Region"]["C2"].value.startswith("=SUMIFS(")
    assert wb["Summary"]._charts, "the attendance chart is present"
    venues = [row for row in wb["By Venue"].iter_rows(min_row=2, values_only=True)]
    assert len(venues) == 8 and all(isinstance(v[4], int) for v in venues)


def test_distribution_is_draft_only(ws):
    run_quarter(ws, "2026Q2")
    drafts = sorted((ws.outbox / "2026Q2").glob("*.eml"))
    assert len(drafts) == 3
    for d in drafts:
        msg = message_from_bytes(d.read_bytes())
        assert msg["Subject"].startswith("[DRAFT - NOT SENT]") and msg["To"].endswith("@example.org")


def test_every_run_leaves_a_manifest(ws):
    r = run_quarter(ws, "2026Q2")
    m = json.loads((ws.root / "runs" / r.run_dir.split("\\")[-1].split("/")[-1] / "manifest.json")
                   .read_text(encoding="utf-8"))
    assert m["synthetic"] is True and len(m["inputs"]) == 16 and m["verdict"] == "READY FOR APPROVAL"
    assert [s["name"] for s in m["stages"]] == ["discover", "ingest", "validate", "compare", "build",
                                               "draft_distribution", "approve"]


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "2026Q3: BLOCKED" in out and "2026Q3: APPROVED v1" in out and "ALREADY APPROVED" in out
