"""Experiments: edits must hit something, a refused edit leaves the data alone, and a real experiment changes
the real pipeline's output - and only the lines it should."""

from __future__ import annotations

import sqlite3
import time

import pytest
from civicworks_lab import experiments, server


def test_an_edit_that_matches_nothing_is_an_error_not_a_silent_pass(tmp_path):
    (tmp_path / "a.csv").write_text("id,v\nX1,1\n", encoding="utf-8")
    with pytest.raises(experiments.ExperimentError):
        experiments.apply(tmp_path, [{"csv": "a.csv", "where": {"id": "NOPE"}, "set": {"v": "2"}}])
    with pytest.raises(experiments.ExperimentError):
        experiments.apply(tmp_path, [{"csv": "a.csv", "where": {"missing_column": "X1"}, "set": {"v": "2"}}])


def test_a_refused_database_edit_changes_nothing(tmp_path):
    con = sqlite3.connect(tmp_path / "d.sqlite")
    con.executescript("CREATE TABLE p (id TEXT PRIMARY KEY); CREATE TABLE c (id TEXT, p TEXT REFERENCES p(id));"
                      "INSERT INTO p VALUES ('A'); INSERT INTO c VALUES ('1', 'A');")
    con.close()
    with pytest.raises(sqlite3.IntegrityError):
        experiments.apply(tmp_path, [{"sqlite": "d.sqlite", "sql": "PRAGMA foreign_keys = ON; UPDATE c SET p = 'Z'"}])
    assert sqlite3.connect(tmp_path / "d.sqlite").execute("SELECT p FROM c").fetchone()[0] == "A"


def test_compare_ignores_hashes_and_times_and_keeps_scene_context():
    a = [{"scene": 1, "text": "== 1. Load"}, {"scene": 1, "text": "  sha256 0123456789abcdef at 2026-11-24T10:00:00Z"},
         {"scene": 2, "text": "== 2. Check"}, {"scene": 2, "text": "  2 findings"}]
    b = [{"scene": 1, "text": "== 1. Load"}, {"scene": 1, "text": "  sha256 fedcba9876543210 at 2026-11-24T11:30:00Z"},
         {"scene": 2, "text": "== 2. Check"}, {"scene": 2, "text": "  3 findings"}]
    out = experiments.compare(a, b)
    assert [x["kind"] for x in out] == ["heading", "removed", "added"]
    assert out[0]["text"] == "== 2. Check"


def test_a_real_experiment_changes_the_real_output():
    ids = server.start_experiment("ledgerguard", "blank-serial")
    normal, test = server.ACTIVE[ids["normal"]], server.ACTIVE[ids["experiment"]]
    end = time.time() + 120
    while (normal.status != "done" or test.status != "done") and time.time() < end:
        time.sleep(0.2)
    assert normal.exit_code == 0 and test.exit_code == 0
    assert test.applied and not test.applied.get("error")
    edited = next(r for r in test.applied["rows"] if r["source"].endswith("::equipment"))
    assert edited["n_changed"] == 1 and edited["changed"][0]["row"][0] == "EQ-0001"
    added = [x["text"] for x in server.compare_runs(normal, test) if x["kind"] == "added"]
    assert any("EQ-0001 missing serial" in t for t in added)
