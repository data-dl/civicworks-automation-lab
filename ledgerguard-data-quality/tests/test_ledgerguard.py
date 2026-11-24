"""LedgerGuard: an export is proven before it is trusted; archives restore only when intact."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import pytest
from openpyxl import load_workbook

from ledgerguard import sources
from ledgerguard.cli import main
from ledgerguard.jobs import Workspace, prove, restore, run_day

D1, D2 = date(2026, 11, 23), date(2026, 11, 24)


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path / "ws")
    sources.generate(w.sources, seed=5)
    return w


def job(day, code):
    return next(j for j in day.jobs if j.code == code)


def test_same_seed_same_sources(tmp_path):
    a, b = Workspace(tmp_path / "a"), Workspace(tmp_path / "b")
    sources.generate(a.sources, 4)
    sources.generate(b.sources, 4)
    assert (a.sources / "authorizations.csv").read_bytes() == (b.sources / "authorizations.csv").read_bytes()


@pytest.mark.parametrize("content, expected, reason", [
    (None, 3, "no file"),
    ("equipment_id,class_code\n", 3, "header but no rows"),
    ("equipment_id,klass\nA,x\nB,y\nC,z\n", 3, "columns changed"),
    ("equipment_id,class_code\nA,x\n", 3, "1 rows exported, the source has 3"),
    ("equipment_id,class_code\nA,x\n,y\nC,z\n", 3, "blank equipment_id"),
])
def test_a_file_existing_is_not_success(tmp_path, content, expected, reason):
    path = tmp_path / "e.csv"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    ok, _, why = prove(path, ["equipment_id", "class_code"], expected, "equipment_id")
    assert not ok and reason in why


def test_a_healthy_day_finds_every_planted_problem(ws):
    day = run_day(ws, D1)
    assert all(j.state == "verified" for j in day.jobs)
    details = [e["detail"] for j in day.jobs for e in j.exceptions]
    assert any("SAW at Wharfside with nobody authorised" in d for d in details)
    assert any("missing serial" in d for d in details) and any("missing last service date" in d for d in details)
    assert any("registered as" in d for d in details)
    assert any(d.startswith("T-007") for d in details)
    files = {p.name for p in ws.current.iterdir()}
    assert {"exceptions.xlsx", "dashboard.html", "MANIFEST.json", "attribute_completeness.csv"} <= files
    wb = load_workbook(ws.current / "exceptions.xlsx")
    assert wb.sheetnames[0] == "Summary" and len(wb.sheetnames) == 5


@pytest.mark.parametrize("mode", ["empty", "renamed-column", "truncated"])
def test_a_bad_desk_export_is_quarantined_and_yesterday_kept(ws, mode):
    run_day(ws, D1)
    good = (ws.current / "attribute_completeness.csv").read_bytes()
    day = run_day(ws, D2, desk_mode=mode)
    j = job(day, "attribute_completeness")
    assert j.state == "quarantined" and j.reason
    assert (ws.quarantine / "2026-11-24" / "attribute_completeness.csv").exists()
    assert (ws.current / "attribute_completeness.csv").read_bytes() == good
    status = json.loads((ws.current / "MANIFEST.json").read_text(encoding="utf-8"))["status"]
    assert status["attribute_completeness"]["stale"] is True
    assert all(job(day, c).state == "verified" for c in ("qualification_mapping", "category_overlaps",
                                                          "active_eligibility"))


def test_every_job_is_logged_with_expected_and_observed(ws):
    run_day(ws, D1)
    run_day(ws, D2, desk_mode="empty")
    con = sqlite3.connect(ws.db)
    rows = con.execute("SELECT run_id, state, expected_rows, observed_rows FROM export_job "
                       "WHERE job_code = 'attribute_completeness' ORDER BY run_id").fetchall()
    assert rows == [("2026-11-23", "verified", 120, 120), ("2026-11-24", "quarantined", 120, 0)]
    assert con.execute("SELECT COUNT(*) FROM archive_item").fetchone()[0] == 6


def test_restore_refuses_a_tampered_archive_and_restores_an_intact_one(ws):
    run_day(ws, D1)
    run_day(ws, D2)
    run_day(ws, date(2026, 11, 25))
    victim = ws.archive / "2026-11-24" / "category_overlaps.csv"
    victim.write_text("tampered\n", encoding="utf-8")
    ok, note = restore(ws, "2026-11-24")
    assert not ok and "no longer match" in note
    ok, note = restore(ws, "2026-11-23")
    assert ok
    manifest = json.loads((ws.current / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "2026-11-23"
    assert (ws.archive / "2026-11-25-replaced-by-restore").exists()


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "d")]) == 0
    out = capsys.readouterr().out
    assert "header but no rows" in out and "columns changed" in out and "restore 2026-11-23: OK" in out
