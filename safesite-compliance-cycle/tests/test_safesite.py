"""SafeSite: reminders, checks, late returns, the two report variants, and the draft/final separation."""

from __future__ import annotations

from datetime import date
from email import message_from_bytes

import pytest
from docx import Document

from safesite import synth
from safesite.cli import arrivals, main
from safesite.cycle import Workspace, check_return, plan_quarter, quarter_bounds, run_cycle
from safesite.reports import produce

Q = synth.QUARTER


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "ws")
    con = workspace.open()
    workspace.facilities = synth.build_consortium(con, 3)
    plan_quarter(con, Q, synth.DUE)
    con.close()
    return workspace


def step(ws, day):
    synth.deliver(ws.submissions, ws.facilities, day, 3)
    return run_cycle(ws, Q, day, arrivals())


def test_quarter_bounds():
    assert quarter_bounds("2026Q4") == (date(2026, 10, 1), date(2026, 12, 31))
    assert quarter_bounds("2026Q1") == (date(2026, 1, 1), date(2026, 3, 31))


@pytest.mark.parametrize("problem, expected", [("missing_evidence", "no evidence reference"),
                                               ("totals_mismatch", "Totals says"),
                                               ("bad_severity", "severity 'HIGH'")])
def test_each_bad_return_is_refused_with_a_reason(tmp_path, problem, expected):
    path = synth.write_return(tmp_path / "r.xlsx", "F99", "workshop", 1, problem)
    result = check_return(path, *quarter_bounds(Q))
    assert not result.ok and any(expected in p for p in result.problems)


def test_a_clean_return_passes(tmp_path):
    path = synth.write_return(tmp_path / "r.xlsx", "F99", "depot", 1, None)
    assert check_return(path, *quarter_bounds(Q)).ok


def test_reminders_follow_the_calendar_and_are_never_duplicated(ws):
    early = step(ws, date(2026, 11, 20))
    assert early.reminders == [], "nothing is due a reminder more than 14 days out"
    first = step(ws, date(2026, 12, 1))
    kinds = {kind for _, kind in first.reminders}
    assert kinds == {"T-14", "correction"}
    assert step(ws, date(2026, 12, 1)).reminders == []
    assert {k for _, k in step(ws, date(2026, 12, 12)).reminders} == {"T-3"}
    overdue = step(ws, date(2026, 12, 18))
    assert sorted(f for f, k in overdue.reminders if k == "overdue") == ["F11", "F12"]


def test_overdue_drafts_copy_the_safety_lead_and_nothing_is_sent(ws):
    for day in (date(2026, 12, 1), date(2026, 12, 18)):
        step(ws, day)
    draft = next((ws.outbox / Q).glob("*F11-overdue.eml"))
    msg = message_from_bytes(draft.read_bytes())
    assert "safety.lead@example.org" in msg["To"] and msg["Subject"].startswith("[DRAFT - NOT SENT]")


def test_late_returns_are_accepted_but_marked_late(ws):
    for day in (date(2026, 12, 1), date(2026, 12, 12), date(2026, 12, 18), date(2026, 12, 20)):
        report = step(ws, day)
    assert report.states == {"accepted": 10, "accepted-late": 2}


def test_finals_need_every_return_and_are_never_overwritten(ws):
    step(ws, date(2026, 12, 18))
    blocked = produce(ws, Q, approve_as="safety lead")
    assert blocked.verdict == "BLOCKED" and not (ws.final / Q).exists()
    assert len(blocked.drafts) == 2 and (ws.qa / Q / f"QA_pack_{Q}.md").exists()
    step(ws, date(2026, 12, 20))
    done = produce(ws, Q, approve_as="safety lead")
    assert done.verdict.startswith("FINAL") and len(done.finals) == 2
    before = {p.name: p.read_bytes() for p in (ws.final / Q).iterdir()}
    assert produce(ws, Q, approve_as="safety lead").verdict.startswith("ALREADY FINAL")
    assert {p.name: p.read_bytes() for p in (ws.final / Q).iterdir()} == before


def test_the_two_report_variants_differ_in_content(ws):
    step(ws, date(2026, 12, 20))
    produce(ws, Q)
    workshop = Document(ws.working / Q / f"workshop_{Q}_draft.docx")
    depot = Document(ws.working / Q / f"depot_{Q}_draft.docx")
    headings = lambda d: [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]  # noqa: E731
    assert "Significant and urgent observations" in headings(workshop)
    assert "Open actions by area" in headings(depot) and "Loading and vehicle areas" in headings(depot)
    assert "SYNTHETIC" in workshop.sections[0].header.paragraphs[0].text


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "BLOCKED - F11 is overdue" in out and "FINAL (approved by safety lead)" in out
    assert "0 new drafts" in out and "ALREADY FINAL" in out
