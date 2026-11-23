"""OpsPilot: the registry, the planner, approvals, checkpoints and resume, project blocks, refusals."""

from __future__ import annotations

import sqlite3

import pytest

from opspilot import dashboard
from opspilot.cli import main
from opspilot.executor import OpsPilot, SimulatedCrash
from opspilot.registry import (
    LanguageModelPlanner,
    Plan,
    Refused,
    Step,
    check_inputs,
    load_registry,
    validate_plan,
)

TOOLS, GOALS = load_registry()


def test_every_goal_in_the_registry_validates():
    from opspilot.registry import RulesPlanner

    planner = RulesPlanner(GOALS)
    for goal in GOALS:
        steps = validate_plan(planner.plan(goal), TOOLS)
        seen = set()
        for s in steps:
            assert set(s.after) <= seen, f"{s.id} runs before what it waits for"
            seen.add(s.id)


def test_plans_with_unknown_tools_or_cycles_are_refused():
    with pytest.raises(Refused, match="not a registered tool"):
        validate_plan(Plan("x", "", [Step("a", "shell.exec", "p")]), TOOLS)
    with pytest.raises(Refused, match="cycle"):
        validate_plan(Plan("x", "", [Step("a", "openbadge.init", "p", ["b"]),
                                     Step("b", "openbadge.init", "p", ["a"])]), TOOLS)


@pytest.mark.parametrize("inputs, message", [
    ({"workspace": "../../Windows"}, "outside"),
    ({"workspace": "openbadge", "extra": 1}, "does not declare"),
    ({}, "missing input"),
])
def test_inputs_are_type_checked(tmp_path, inputs, message):
    with pytest.raises(Refused, match=message):
        check_inputs(TOOLS["openbadge.init"], inputs, tmp_path)


def test_quarter_and_role_inputs_are_validated(tmp_path):
    tool = TOOLS["regional.approve"]
    with pytest.raises(Refused, match="not a quarter"):
        check_inputs(tool, {"workspace": "regional", "quarter": "Q2", "role": "director"}, tmp_path)
    with pytest.raises(Refused, match="not an approver role"):
        check_inputs(tool, {"workspace": "regional", "quarter": "2026Q2", "role": "rm -rf /"}, tmp_path)


def test_language_model_planner_is_off_by_default(monkeypatch):
    monkeypatch.delenv("OPSPILOT_LLM", raising=False)
    with pytest.raises(Refused, match="disabled"):
        LanguageModelPlanner().plan("publish-cycle")


@pytest.fixture(scope="module")
def control(tmp_path_factory):
    """One publish-cycle run, taken through approval, a crash and a resume; shared by the tests below."""
    ops = OpsPilot(tmp_path_factory.mktemp("control"))
    run_id = ops.start("publish-cycle")
    first = ops.run(run_id)
    for step, role in (("badge-release", "release manager"), ("regional-approve", "program director")):
        ops.approve(run_id, step, role)
    with pytest.raises(SimulatedCrash):
        ops.run(run_id, crash_after="badge-release")
    state_after_crash = ops.con.execute("SELECT state FROM execution WHERE run_id = ?", (run_id,)).fetchone()[0]
    final = ops.run(run_id)
    return {"ops": ops, "run": run_id, "first": first, "crash_state": state_after_crash, "final": final}


def test_publish_steps_wait_for_a_person(control):
    first = control["first"]
    assert first.state == "awaiting-approval"
    waiting = {o.step for o in first.outcomes if o.status == "awaiting-approval"}
    assert waiting == {"badge-release", "regional-approve"}
    assert all(o.status == "done" for o in first.outcomes if o.step not in waiting)


def test_a_crash_is_recorded_and_resume_skips_verified_work(control):
    assert control["crash_state"] == "interrupted"
    final = control["final"]
    assert final.state == "complete"
    rerun = [o.step for o in final.outcomes if "not re-run" not in o.note]
    assert rerun == ["regional-approve"], "only the step after the crash runs again"


def test_projects_record_the_approver_role(control):
    ops = control["ops"]
    con = sqlite3.connect(ops.workspaces / "regional" / "regional.sqlite")
    assert con.execute("SELECT approved_by FROM report_release").fetchone()[0] == "program director"
    con.close()


def test_a_changed_output_makes_the_checkpoint_stale(control):
    ops, run_id = control["ops"], control["run"]
    feed = ops.workspaces / "masterrecord" / "feeds" / "2026-11" / "registry.csv"
    original = feed.read_bytes()
    feed.write_bytes(original + b"\n")
    try:
        summary = ops.run(run_id)
        outcome = {o.step: o for o in summary.outcomes}["master-init"]
        assert "not re-run" not in outcome.note, "a checkpoint whose files changed is not trusted"
        events = [r[0] for r in ops.con.execute("SELECT event_type FROM event_log WHERE run_id = ?", (run_id,))]
        assert "checkpoint-stale" in events
    finally:
        feed.write_bytes(original)


def test_a_projects_own_block_stops_the_run(tmp_path):
    ops = OpsPilot(tmp_path / "c")
    run_id = ops.start("roster-cycle")
    ops.approve(run_id, "roster-commit", "membership lead")
    summary = ops.run(run_id)
    assert summary.state == "blocked"
    assert {o.step: o.status for o in summary.outcomes}["roster-commit"] == "blocked"
    assert "roster-commit" in summary.next_action and (ops.root / "logs" / run_id / "HANDOFF.md").exists()


def test_direct_requests_and_history_edits_are_refused(control):
    ops = control["ops"]
    for name, inputs in (("shell.exec", {"command": "x"}), ("openbadge.release", {"workspace": "openbadge"}),
                         ("openbadge.init", {"workspace": "../.."})):
        with pytest.raises(Refused):
            ops.request(name, **inputs)
    with pytest.raises(Refused, match="does not publish"):
        ops.approve(control["run"], "master-init", "anyone")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        ops.con.execute("UPDATE event_log SET event_type = 'x'")
    refusals = ops.con.execute("SELECT COUNT(*) FROM event_log WHERE event_type = 'refused'").fetchone()[0]
    assert refusals >= 3


def test_status_page_is_built(control):
    page = dashboard.build(control["ops"])
    text = page.read_text(encoding="utf-8")
    assert "publish-cycle" in text and "APR-0001" in text and "SYNTHETIC" in text


def test_demo_runs(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "COMPLETE" in out and "BLOCKED" in out and out.count("REFUSED") >= 6
