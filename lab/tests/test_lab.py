"""The Lab: content loads, a guided run pauses between scenes, previews work, and access stays confined."""

from __future__ import annotations

import time

import pytest
from civicworks_lab import server


def wait(run, status, timeout=60):
    end = time.time() + timeout
    while run.status != status and time.time() < end:
        time.sleep(0.1)
    return run.status


def test_content_has_every_pipeline_and_matching_scenes():
    keys = [p["key"] for p in server.CONTENT["pipelines"]]
    assert keys == ["atlas", "openbadge", "regional", "ledgerguard", "safesite", "masterrecord", "reconcilehub",
                    "opspilot"]
    assert len(server.CONTENT["glossary"]) >= 50 and len(server.CONTENT["ideas"]) == 9
    for p in server.CONTENT["pipelines"]:
        assert p["scenes"] and all({"explain", "predict", "answer"} <= set(s) for s in p["scenes"].values())


def test_a_guided_run_pauses_between_scenes_and_reports_changes():
    run = server.start_run("reconcilehub")
    try:
        assert wait(run, "paused") == "paused" and run.scene == 1
        assert run.changes[1]["added"], "scene 1 writes the three input files"
        server.next_scene(run)
        assert wait(run, "paused") == "paused" and run.scene == 2
        assert any("reconcile.sqlite::" in t["table"] for t in run.changes[2]["tables"])
        for _ in range(5):
            server.next_scene(run)
            wait(run, "paused", 30) if run.scene < 6 else None
        assert wait(run, "done") == "done" and run.exit_code == 0
        assert any(line["text"].startswith("== 7.") for line in run.lines)
    finally:
        if run.proc.poll() is None:
            run.proc.kill()


def test_previews_and_confinement():
    run = server.start_run("regional")
    try:
        wait(run, "paused")
        server.next_scene(run)
        wait(run, "paused")
        xlsx = next(p for p in run.workspace.rglob("Studio_2026Q2.xlsx"))
        preview = server.preview(xlsx)
        assert preview["kind"] == "table" and any(c.startswith("ƒ =SUM") for s in preview["sheets"]
                                                  for r in s["rows"] for c in r)
        db = server.preview(run.workspace / "regional.sqlite")
        assert db["kind"] == "sqlite" and any(t["foreign_keys"] for t in db["tables"])
        with pytest.raises(PermissionError):
            server.confined(run, "../../../README.md")
    finally:
        run.proc.kill()


def test_only_registered_pipelines_can_start():
    with pytest.raises(ValueError):
        server.start_run("shell")
