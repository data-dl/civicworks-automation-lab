"""ReconcileHub: normalisation, every held case, decisions, approval, idempotent re-runs, supersede."""

from __future__ import annotations

import csv

import pytest
from openpyxl import load_workbook

from reconcilehub import synth
from reconcilehub.cli import main
from reconcilehub.commit import commit
from reconcilehub.reconcile import Workspace, norm_id, norm_name, reconcile, record_decisions, similarity

C = synth.CYCLE


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "ws")
    synth.build_inputs(workspace.inputs, seed=2)
    return workspace


def decide(ws, choices: dict[str, str]):
    path = ws.inputs / C / "d.csv"
    r = reconcile(ws, C)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "disposition", "reviewer"])
        for c in r.held:
            w.writerow([c.case_id, choices.get(c.kind, "exclude"), "tester"])
    assert record_decisions(ws, C, path) == []


def actions(r, kind):
    return [a for a in r.actions if a["action"] == kind]


@pytest.mark.parametrize("raw, expected", [(" fc-17 ", "FC-00017"), ("FC00031", "FC-00031"),
                                           ("FC-00931", "FC-00931"), ("", None), ("XX-1", None)])
def test_ids_normalise_and_bad_ones_are_rejected(raw, expected):
    assert norm_id(raw) == expected


def test_names_normalise_without_losing_meaning():
    assert norm_name("  Kit   LARKSPURNE ") == "kit larkspurne"
    assert norm_name("Rue Ashgrove-Vale") == norm_name("rue ashgrove vale")
    assert similarity("Quin Brindlecote", "Quin Brindlecot") > 0.9 > similarity("Quin Brindlecote", "Arlo Mossgrave")


def test_exact_matches_are_decided_and_the_rest_held(ws):
    r = reconcile(ws, C)
    assert {c.kind for c in r.held} == {"possible-id-change", "missing-id", "possible-duplicate"}
    assert [a["member_id"] for a in actions(r, "REMOVE")] == ["FC-00051"]
    assert [a["member_id"] for a in actions(r, "CHANGE ROLE")] == ["FC-00013"]
    assert sorted(a["member_id"] for a in actions(r, "ADD")) == ["FC-00060", "FC-00061"]
    assert r.normalised_ids == 1
    assert not any(a["member_id"] in ("FC-00031", "FC-00931", "FC-00041") for a in r.actions), \
        "nothing is added or removed for people in a held case"


def test_same_name_different_ids_are_kept_apart(ws):
    r = reconcile(ws, C)
    assert any("share a name; kept as different people" in n for n in r.notes)
    assert "FC-00005" in r.approved and "FC-00059" in r.approved


def test_commit_is_blocked_while_anything_is_held_and_admins_get_a_draft(ws):
    res = commit(ws, C, "lead")
    assert res.verdict.startswith("BLOCKED") and res.drafts
    assert not (ws.snapshots / C).exists()


def test_same_person_decisions_become_rename_and_fix_actions(ws):
    decide(ws, {"possible-id-change": "same-person", "missing-id": "same-person", "possible-duplicate": "same-person"})
    r = reconcile(ws, C)
    assert not r.held
    assert [a["member_id"] for a in actions(r, "RENAME ID")] == ["FC-00931"]
    assert [a["member_id"] for a in actions(r, "FIX ID")] == ["FC-00041"]
    assert "FC-00031" not in r.approved and "FC-00931" in r.approved


def test_different_person_restores_the_old_member_and_removes_the_new_id(ws):
    decide(ws, {"possible-id-change": "different-person"})
    r = reconcile(ws, C)
    assert "FC-00031" in [a["member_id"] for a in actions(r, "ADD")]
    assert "FC-00931" in [a["member_id"] for a in actions(r, "REMOVE")]


def test_approval_writes_snapshot_workbook_and_report(ws):
    decide(ws, {"possible-id-change": "same-person", "missing-id": "same-person", "possible-duplicate": "same-person"})
    res = commit(ws, C, "lead")
    assert res.verdict.startswith("APPROVED v1")
    wb = load_workbook(ws.exports / C / f"Access_import_{C}_v1.xlsx")
    assert wb.sheetnames == ["About", "Import", "Reviewed cases", "Approved roster"]
    imported = {row[0] for row in wb["Import"].iter_rows(min_row=2, values_only=True)}
    assert imported == {"ADD", "REMOVE", "CHANGE ROLE", "RENAME ID", "FIX ID"}
    assert (ws.snapshots / C / "v1" / "approved_roster.csv").exists()


def test_reruns_are_idempotent_and_changes_need_supersede(ws):
    decide(ws, {"possible-id-change": "same-person", "missing-id": "same-person", "possible-duplicate": "same-person"})
    first = commit(ws, C, "lead")
    assert commit(ws, C, "lead").verdict.startswith("NOTHING NEW")
    synth.late_registration(ws.inputs)
    assert commit(ws, C, "lead").verdict.startswith("REFUSED")
    second = commit(ws, C, "lead", supersede="late registration")
    assert second.verdict.startswith("APPROVED v2") and first.version == 1
    assert (ws.snapshots / C / "v1" / "approved_roster.csv").exists()


def test_bad_decision_lines_are_reported(ws):
    reconcile(ws, C)
    path = ws.inputs / C / "bad.csv"
    path.write_text("case_id,disposition,reviewer\nnope,same-person,x\nmissing-id:FC-00041->row 42,merge,x\n",
                    encoding="utf-8")
    problems = record_decisions(ws, C, path)
    assert len(problems) == 2


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "BLOCKED: 3 case(s)" in out and "NOTHING NEW" in out and "APPROVED v2" in out
