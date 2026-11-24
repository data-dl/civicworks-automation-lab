"""OpenBadge: every release path, including the ones that must fail safely."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import pytest

from openbadge import synth
from openbadge.cli import main
from openbadge.db import connect, current_version, migrate
from openbadge.registry import build_payload, canonical_bytes
from openbadge.release import Workspace, consume, release, rollback, status_rows
from openbadge.site import read_pointer

AS_OF = date(2026, 11, 23)


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "ws")
    con = workspace.open()
    synth.seed_database(con, seed=7, learners=40)
    con.close()
    return workspace


def test_same_seed_same_bytes(tmp_path):
    payloads = []
    for name in ("a", "b"):
        con = connect(tmp_path / f"{name}.sqlite")
        migrate(con)
        synth.seed_database(con, seed=11, learners=30)
        payloads.append(canonical_bytes(build_payload(con, "R0001", AS_OF)))
        con.close()
    assert payloads[0] == payloads[1]


def test_migrations_apply_once_and_foreign_keys_hold(tmp_path):
    con = connect(tmp_path / "m.sqlite")
    assert migrate(con) == [1] and migrate(con) == [] and current_version(con) == 1
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO badge (badge_id, learner_id, badge_type, issue_date, expiry_date, status) "
                    "VALUES ('LSA-00000000', 'nobody', 'KILN-SAFETY', '2026-01-01', '2027-01-01', 'approved')")


def test_first_release_is_verified_before_the_pointer_moves(ws):
    r = release(ws, AS_OF)
    assert r.verdict == "PUBLISHED" and r.pointer == "R0001"
    pointer = read_pointer(ws.site)
    data = (ws.site / pointer["path"]).read_bytes()
    assert pointer["sha256"] == r.sha256 and json.loads(data)["record_count"] == r.record_count
    manifest = json.loads((ws.runs / "R0001" / "manifest.json").read_text(encoding="utf-8"))
    assert [s["name"] for s in manifest["stages"]] == ["snapshot", "validate", "publish_data",
                                                       "verify_over_http", "switch_pointer"]
    assert manifest["synthetic"] is True and "site/latest.json" in manifest["outputs"]


def test_bad_data_blocks_and_nothing_is_published(ws):
    release(ws, AS_OF)
    con = ws.open()
    dup, bad = synth.plant_duplicate(con), synth.plant_invalid_date(con)
    con.close()
    r = release(ws, AS_OF)
    assert r.verdict == "BLOCKED"
    rules = {f.rule for f in r.findings if f.severity == "blocking"}
    assert rules == {"unique_badge_id", "valid_dates"}
    assert any(dup in f.detail for f in r.findings) and any(bad in f.detail for f in r.findings)
    assert read_pointer(ws.site)["release_id"] == "R0001"
    assert not (ws.site / "releases" / "registry-R0002.json").exists()


def test_a_badge_with_an_unknown_type_blocks_instead_of_vanishing(ws):
    # Found by the Lab's "unknown badge type" experiment: an inner join used to drop such a badge silently,
    # so the release went out one badge short with no finding. Written outside the app's connection, as a
    # bulk load or a hand edit would, where foreign keys are not switched on.
    raw = sqlite3.connect(ws.db)
    raw.execute("UPDATE badge SET badge_type = 'GLASS-WIZARD' WHERE row_id = 1")
    raw.commit()
    raw.close()
    r = release(ws, AS_OF)
    assert r.verdict == "BLOCKED"
    assert any(f.rule == "controlled_vocabulary" and "GLASS-WIZARD" in f.detail for f in r.findings)
    assert read_pointer(ws.site) is None, "nothing went live"


@pytest.mark.parametrize("fault", ["corrupt-after-write", "missing-file"])
def test_a_broken_upload_never_becomes_latest(ws, fault):
    release(ws, AS_OF)
    r = release(ws, AS_OF, inject=fault)
    assert r.verdict == "VERIFY-FAILED"
    assert read_pointer(ws.site)["release_id"] == "R0001"
    assert list(ws.tickets.glob("T*-R0002-verify-failed.md"))
    assert consume(ws).verdict == "accepted", "consumers still get the last good release"


def test_a_large_drop_needs_explicit_acceptance(ws):
    release(ws, AS_OF)
    con = ws.open()
    con.execute("UPDATE badge SET status = 'revoked' WHERE row_id % 3 = 0")
    con.commit()
    con.close()
    assert release(ws, AS_OF).verdict == "BLOCKED"
    assert release(ws, AS_OF, accept_drop=True).verdict == "PUBLISHED"


def test_dry_run_publishes_nothing(ws):
    r = release(ws, AS_OF, apply=False)
    assert r.verdict == "DRY-RUN" and read_pointer(ws.site) is None
    assert not (ws.site / "releases").exists()


def test_delayed_consumer_keeps_technical_and_business_status_apart(ws):
    release(ws, AS_OF)
    assert consume(ws, delayed=True).verdict == "pending"
    row = status_rows(ws)[0]
    assert row["technical"] == "verified" and row["consumer"] == "pending"
    assert consume(ws, delayed=True).verdict == "accepted"
    assert status_rows(ws)[0]["consumer"] == "accepted"


def test_stale_pointer_is_rejected_by_the_consumer_and_rollback_recovers(ws):
    release(ws, AS_OF)
    con = ws.open()
    synth.issue_new_badges(con, seed=3, count=5)
    con.close()
    release(ws, AS_OF)
    live = ws.site / read_pointer(ws.site)["path"]
    live.unlink()  # someone deleted the live file: the pointer is now stale
    c = consume(ws)
    assert c.verdict == "rejected" and c.reason.startswith("missing_target") and c.ticket
    refused = rollback(ws, to="R0002")
    assert not refused.ok and "missing or changed" in refused.reason
    ok = rollback(ws)
    assert ok.ok and ok.target == "R0001"
    assert consume(ws).verdict == "accepted"


def test_rollback_refuses_a_release_that_never_verified_or_was_altered(ws):
    release(ws, AS_OF)
    release(ws, AS_OF, inject="corrupt-after-write")
    assert not rollback(ws, to="R0002").ok
    (ws.site / "releases" / "registry-R0001.json").write_text("{}", encoding="utf-8")
    result = rollback(ws, to="R0001")
    assert not result.ok and "missing or changed" in result.reason


def test_release_files_are_immutable(ws):
    release(ws, AS_OF)
    con = ws.open()
    con.execute("INSERT INTO registry_release (release_id, technical_status, created_at) "
                "VALUES ('R0002', 'blocked', 'x')")
    con.commit()
    con.close()
    (ws.site / "releases" / "registry-R0003.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        release(ws, AS_OF)


def test_demo_command_runs_end_to_end(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path / "demo")]) == 0
    out = capsys.readouterr().out
    assert "R0002: BLOCKED" in out and "R0003: VERIFY-FAILED" in out and "REFUSED" in out
    assert "pointer moved R0004 -> R0001" in out
