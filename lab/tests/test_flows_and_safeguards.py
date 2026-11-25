"""The flows point at real code, every safeguard is on unless switched off for one run, switching one off
really changes what the pipeline does, and private prep stays private."""

from __future__ import annotations

import importlib
import time

from civicworks_lab import flows, server


def test_every_flow_step_resolves_to_real_code_and_every_pipeline_has_a_safeguard():
    data = flows.load()                      # raises if a function, focus line or database object has gone
    assert set(data) == set(server.PROJECTS)
    for key, flow in data.items():
        assert flow["shape"] and flow["nodes"]
        assert all(n.get("source", {}).get("text") for n in flow["nodes"]), key
        switches = [n for n in flow["nodes"] if n.get("switch")]
        assert len(switches) == 1 and switches[0]["switch"]["look_for"] != "TBD", key


def test_safeguards_are_on_by_default_and_announce_themselves_when_off(monkeypatch, capsys):
    runkit = importlib.import_module("ledgerguard.runkit")
    monkeypatch.delenv("CIVICWORKS_SAFEGUARD_OFF", raising=False)
    assert runkit.guard("row-count-proof") is True
    monkeypatch.setenv("CIVICWORKS_SAFEGUARD_OFF", "row-count-proof")
    runkit._ANNOUNCED.discard("row-count-proof")
    assert runkit.guard("row-count-proof") is False and runkit.guard("something-else") is True
    assert runkit.guard("row-count-proof") is False
    assert capsys.readouterr().out.count("TEACHING SWITCH") == 1


def test_switching_a_safeguard_off_changes_the_real_run():
    ids = server.start_experiment("ledgerguard", "off-row-proof")
    normal, off = server.ACTIVE[ids["normal"]], server.ACTIVE[ids["experiment"]]
    end = time.time() + 120
    while (normal.status != "done" or off.status != "done") and time.time() < end:
        time.sleep(0.2)
    added = [x["text"] for x in server.compare_runs(normal, off) if x["kind"] == "added"]
    assert any("attribute_completeness" in t and " ok " in t and "0/120" in t for t in added), added
    assert not any("TEACHING SWITCH" in x["text"] for x in server.compare_runs(normal, off))


def test_private_prep_is_optional_and_notes_stay_in_its_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PREP", tmp_path / "missing")
    assert server.load_prep() is None
    prep = tmp_path / "prep"
    prep.mkdir()
    (prep / "interview.yaml").write_text("pitch_30s: hello\n", encoding="utf-8")
    monkeypatch.setattr(server, "PREP", prep)
    assert server.load_prep()["interview"]["pitch_30s"] == "hello"
    server.save_note("map-atlas", "like our provider directory")
    assert server.read_notes() == {"map-atlas": "like our provider directory"}
    assert not (server.ROOT / "my-notes.json").exists()
