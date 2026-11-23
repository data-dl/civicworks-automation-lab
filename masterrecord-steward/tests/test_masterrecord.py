"""MasterRecord Steward: precedence, holds, decisions, and a write-back that disturbs nothing else."""

from __future__ import annotations

import csv
from datetime import date

import pytest
from openpyxl import load_workbook

from masterrecord import synth
from masterrecord.apply import apply_decisions
from masterrecord.cli import init, main, write_demo_decisions
from masterrecord.runkit import sha256_file
from masterrecord.steward import Workspace, propose, resolve

TODAY = date(2026, 11, 23)
SPEC = {"order": ["registry", "contract"], "authority": "registry", "required": True,
        "allowed": ["Journeyman", "Master", "Fellow", "none"]}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "ws")
    init(workspace, seed=4)
    return workspace


def ids(rows):
    return {r["proposal_id"] for r in rows}


def test_authority_wins_and_the_disagreement_is_recorded():
    kind, value, why = resolve({"registry": {"Master"}, "contract": {"Fellow"}}, SPEC, "Fellow", None)
    assert (kind, value) == ("change", "Master") and "contract says Fellow - not used" in why


def test_without_an_authority_a_disagreement_holds():
    spec = {**SPEC, "authority": None}
    kind, value, why = resolve({"registry": {"Master"}, "contract": {"Fellow"}}, spec, "Fellow", None)
    assert kind == "hold" and value == "" and "disagree" in why


def test_unknown_is_not_the_same_as_ineligible():
    assert resolve({}, SPEC, "", None)[0] == "hold"
    assert resolve({"registry": {"none"}}, SPEC, "Master", None)[:2] == ("change", "none")


def test_values_outside_the_vocabulary_hold():
    assert resolve({"registry": {"Grandmaster"}}, SPEC, "Master", None)[0] == "hold"


def test_fallback_only_fills_a_missing_value():
    spec = {"order": ["registry"], "required": True, "allowed": ["Z1", "Z4"]}
    assert resolve({}, spec, "", "Z4")[:2] == ("change", "Z4")
    assert resolve({}, spec, "Z1", "Z4")[0] == "same", "a fallback never overwrites a value the master already has"


def test_proposal_finds_every_planted_case(ws):
    r = propose(ws, synth.CYCLE)
    assert ids(r.holds) == {"H-GJF-0005-network_affiliation", "H-GJF-0008-inspection_zone",
                            "H-GJF-0011-workshop_type", "H-GJF-0014-certification_class"}
    assert {"P-GJF-0003-certification_class", "P-GJF-0020-inspection_zone", "P-GJF-0022-participation_status",
            "P-GJF-0023-certification_class", "P-GJF-0027-network_affiliation"} == ids(r.changes)
    assert ids(r.excluded) == {"X-GJF-0017-Scope"}
    assert r.duplicates_ignored == 3, "the repeated contract row adds nothing"
    assert (ws.review / f"decisions_{synth.CYCLE}.csv").exists()


def test_nothing_is_written_in_a_dry_run(ws):
    r = propose(ws, synth.CYCLE)
    before = sha256_file(ws.master)
    result = apply_decisions(ws, write_demo_decisions(ws.review / "d.csv", r), today=TODAY)
    assert result.mode == "dry-run" and len(result.planned) == 8 and sha256_file(ws.master) == before


def test_apply_changes_only_decided_cells_and_keeps_everything_else(ws):
    r = propose(ws, synth.CYCLE)
    decisions = write_demo_decisions(ws.review / "d.csv", r)
    result = apply_decisions(ws, decisions, apply=True, today=TODAY)
    assert not result.errors and result.sheet == "Changes 2026-11-23" and result.preserved_cells > 300
    wb = load_workbook(ws.master)
    assert wb.sheetnames == ["Instructions", "Master", "Reference", "Changes 2026-10-26", "Changes 2026-11-23"]
    master = wb["Master"]
    assert master.cell(row=synth.REFERENCE_ROW, column=1).value == "REFERENCE - do not move or delete"
    rows = {master.cell(row=i, column=1).value: i for i in range(2, 32)}
    assert master.cell(row=rows["GJF-0008"], column=7).value == "Z4"
    assert master.cell(row=rows["GJF-0017"], column=8).value == "excluded"
    assert master.cell(row=rows["GJF-0005"], column=9).value == "2026-10-26", "undecided rows untouched"
    assert (ws.backups / result.backup).exists()


def test_applying_the_same_decisions_twice_changes_nothing(ws):
    r = propose(ws, synth.CYCLE)
    decisions = write_demo_decisions(ws.review / "d.csv", r)
    apply_decisions(ws, decisions, apply=True, today=TODAY)
    after_first = sha256_file(ws.master)
    again = apply_decisions(ws, decisions, apply=True, today=TODAY)
    assert again.planned == [] and len(again.already_applied) == 8 and sha256_file(ws.master) == after_first


def test_decided_holds_do_not_come_back(ws):
    r = propose(ws, synth.CYCLE)
    apply_decisions(ws, write_demo_decisions(ws.review / "d.csv", r), apply=True, today=TODAY)
    again = propose(ws, synth.CYCLE)
    assert ids(again.holds) == {"H-GJF-0005-network_affiliation", "H-GJF-0014-certification_class"}
    assert again.changes == [] and again.excluded == []


@pytest.mark.parametrize("line, message", [
    (["H-GJF-0005-network_affiliation", "approve", "", "registrar", "x"], "is a hold"),
    (["H-GJF-0008-inspection_zone", "choose", "Z9", "registrar", "x"], "not allowed"),
    (["P-GJF-0003-certification_class", "approve", "Fellow", "registrar", "x"], "must keep the proposed value"),
    (["P-GJF-0003-certification_class", "approve", "Master", "", ""], "approver role and a rationale"),
    (["P-NOPE", "approve", "x", "registrar", "x"], "no proposal"),
])
def test_bad_decisions_are_refused_and_nothing_is_written(ws, line, message):
    propose(ws, synth.CYCLE)
    path = ws.review / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["proposal_id", "resolution", "value", "approver_role", "rationale"])
        w.writerow(line)
    before = sha256_file(ws.master)
    result = apply_decisions(ws, path, apply=True, today=TODAY)
    assert any(message in e for e in result.errors) and sha256_file(ws.master) == before


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "8 decisions already applied" in out and "holds 2" in out
