"""Atlas: rules, freeze, PDF structure, crash and resume, publish, delta and rollback."""

from __future__ import annotations

import json

import pymupdf
import pytest

from atlas import synth
from atlas.cli import main
from atlas.pdf import plan, read_entries, render, verify
from atlas.release import SimulatedCrash, current, rollback, run
from atlas.stages import Workspace, craft_code, ingest_and_check, phone_token, release_date

P = synth.PERIOD


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path / "ws")
    synth.generate(w.sources, seed=3, members=80)
    return w


def published(ws):
    run(ws, P, approve_as="editor")
    return ws


def test_normalisers():
    assert craft_code("  glass   blowing ") == "GLS" and craft_code("Glasblowing") is None
    assert phone_token("(555) 312 4567") == phone_token("555.3124567") == "555-312-4567"
    assert str(release_date("2026-12")) == "2027-01-01"


def test_same_seed_same_sources(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    synth.generate(a, 9)
    synth.generate(b, 9)
    assert all((a / P / f).read_bytes() == (b / P / f).read_bytes()
               for f in ("members.csv", "studios.csv", "endorsements.csv", "listings.csv"))


def test_every_planted_problem_is_found_and_blocks(ws):
    synth.plant_problems(ws.sources)
    r = ingest_and_check(ws, P)
    blocking = {f.rule for f in r.blocking}
    assert blocking == {"duplicate_member_id", "orphaned_studio", "expired_endorsement", "invalid_dates",
                        "unknown_craft", "contradictory_audience"}
    advisory = {f.rule for f in r.findings if f.severity == "advisory"}
    assert {"missing_venue_token", "possible_duplicate_person"} <= advisory
    assert any("repeated listing" in n for n in r.notes)
    summary = json.loads((ws.qa / P / "qa_summary.json").read_text(encoding="utf-8"))
    assert summary["blocking"] == 6 and (ws.qa / P / "qa_summary.html").exists()
    assert run(ws, P, approve_as="editor").verdict == "STOPPED at check"
    assert not (ws.snapshots / P).exists()


def test_freeze_needs_a_named_approver_and_is_read_only(ws):
    assert run(ws, P).verdict == "STOPPED at freeze"
    r = run(ws, P, approve_as="editor")
    assert r.verdict == "PUBLISHED"
    snap = ws.snapshots / P / "snapshot.sqlite"
    with pytest.raises(PermissionError):
        snap.open("ab")


def test_each_pdf_has_the_structure_a_reader_needs(ws):
    published(ws)
    folder = ws.published / P
    assert len(list(folder.glob("*.pdf"))) == 12
    doc = pymupdf.open(folder / "LM-inspector.pdf")
    assert doc[doc.page_count - 1].get_text().lstrip().startswith("Index")
    assert doc.get_toc()[0] == [1, "Cover", 1] and doc.get_toc()[-1][1] == "Index"
    link = doc[1].get_links()[0]
    assert doc[link["page"]].get_text().lstrip().startswith(doc.get_toc()[2][1])


def test_editions_follow_their_audience_rules(ws):
    published(ws)
    snap = ws.snapshots / P / "snapshot.sqlite"
    public = {e.member_id for e in read_entries(snap, "CR", "public")}
    inspector = read_entries(snap, "CR", "inspector")
    import sqlite3

    con = sqlite3.connect(snap)
    opted_out = {r[0] for r in con.execute("SELECT member_id FROM guild_member WHERE public_opt_in = 0")}
    assert not public & opted_out
    assert {e.state for e in inspector} <= {"active", "suspended"}
    assert all("Endorsement" not in pymupdf.open(ws.published / P / "CR-public.pdf")[2].get_text() for _ in [0])


def test_verify_catches_a_damaged_pdf(ws, tmp_path):
    published(ws)
    snap = ws.snapshots / P / "snapshot.sqlite"
    p = plan("SW", "member", read_entries(snap, "SW", "member"))
    good = tmp_path / "good.pdf"
    render(snap, "SW", "member", P, good)
    assert verify(good, p) == []
    doc = pymupdf.open(good)
    doc.delete_page(doc.page_count - 1)  # lose the index
    bad = tmp_path / "bad.pdf"
    doc.save(bad)
    problems = verify(bad, p)
    assert any("pages" in x for x in problems) and any("index" in x for x in problems)
    bad.write_bytes(b"not a pdf")
    assert verify(bad, p)[0].startswith("cannot open")


def test_a_crash_after_render_resumes_without_redoing_work(ws):
    with pytest.raises(SimulatedCrash):
        run(ws, P, approve_as="editor", crash_after="render")
    assert not (ws.published / P).exists(), "nothing is published before verification"
    r = run(ws, P, approve_as="editor", resume=True)
    assert r.skipped == ["check", "freeze", "render"] and r.verdict == "PUBLISHED"


def test_resume_redoes_a_stage_whose_output_changed(ws):
    with pytest.raises(SimulatedCrash):
        run(ws, P, approve_as="editor", crash_after="render")
    staged = next((ws.staging / P).glob("*.pdf"))
    staged.write_bytes(staged.read_bytes() + b"%tampered")
    r = run(ws, P, approve_as="editor", resume=True)
    assert "render" not in r.skipped and r.verdict == "PUBLISHED"


def test_next_period_reports_changes_and_rollback_is_safe(ws):
    published(ws)
    synth.next_period(ws.sources)
    assert run(ws, "2026-12", approve_as="editor").verdict == "PUBLISHED"
    assert current(ws) == "2026-12"
    changes = (ws.published / "2026-12" / "CHANGES.md").read_text(encoding="utf-8")
    assert "listings added: 3" in changes and "listings withdrawn: 2" in changes
    victim = next((ws.published / P).glob("*.pdf"))
    original = victim.read_bytes()
    victim.write_bytes(original + b"x")
    ok, note = rollback(ws, P)
    assert not ok and "no longer match" in note and current(ws) == "2026-12"
    victim.write_bytes(original)
    ok, _ = rollback(ws, P)
    assert ok and current(ws) == P and (ws.published / "2026-12").exists()


def test_a_frozen_period_is_never_refrozen(ws):
    published(ws)
    from atlas.stages import freeze

    ok, note = freeze(ws, P, "editor")
    assert not ok and "never replaced" in note


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "d")]) == 0
    out = capsys.readouterr().out
    assert "STOPPED at check" in out and "process stopped after render" in out and "rollback to 2026-11: OK" in out
