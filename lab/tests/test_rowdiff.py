"""Row-level changes: exact cells, traced identifiers, and no machine paths in what is shown."""

from __future__ import annotations

import sqlite3

from civicworks_lab import rowdiff


def make(ws, status="held", path_in_cell=False):
    ws.mkdir(exist_ok=True)
    con = sqlite3.connect(ws / "app.sqlite")
    con.execute("CREATE TABLE IF NOT EXISTS case_ (case_id TEXT PRIMARY KEY, status TEXT, note TEXT)")
    con.execute("DELETE FROM case_")
    note = str(ws / "archive" / "x.csv") if path_in_cell else ""
    con.executemany("INSERT INTO case_ VALUES (?,?,?)", [("MC-001", status, note), ("MC-002", "held", "")])
    con.commit()
    con.close()
    (ws / "roster.csv").write_text("person_id,name,period\nP-0101,Ada,2026Q3\nP-0102,Bo,2026Q3\nP-0103,Cy,2026Q3\n"
                                   "P-0104,Di,2026Q3\n", encoding="utf-8")


def test_changed_rows_name_the_exact_cells(tmp_path):
    make(tmp_path)
    before = rowdiff.contents(tmp_path)
    make(tmp_path, status="same-person")
    change = {c["source"]: c for c in rowdiff.changes(before, rowdiff.contents(tmp_path))}
    case = change["app.sqlite::case_"]
    assert case["n_changed"] == 1 and case["n_added"] == case["n_removed"] == 0
    edit = case["changed"][0]
    assert edit["cells"] == [1] and edit["before"][1] == "held" and edit["row"][1] == "same-person"
    assert "roster.csv" not in change, "an untouched file is not reported"


def test_trace_finds_identifiers_but_not_shared_values(tmp_path):
    make(tmp_path)
    traced = rowdiff.trace(rowdiff.contents(tmp_path), "P-0102 failed the check; MC-002 held; period 2026Q3")
    found = {(t["source"], r["token"]) for t in traced for r in t["rows"]}
    assert ("roster.csv", "P-0102") in found and ("app.sqlite::case_", "MC-002") in found
    assert not any(tok == "2026Q3" for _, tok in found), "a value in every row is not a record identifier"


def test_absolute_paths_are_shown_relative_to_the_run(tmp_path):
    make(tmp_path, path_in_cell=True)
    rows = rowdiff.contents(tmp_path)["app.sqlite::case_"]["rows"]
    note = next(r[2] for r in rows.values() if r[2])
    assert note.startswith("<workspace>") and str(tmp_path) not in note
