"""Record every experiment and every pipeline's final database for the presentation site.

For each experiment in learn/experiments.yaml this runs the real demo twice through the Lab's own code - once
as normal, once with the experiment's change - and writes docs/data/experiments/<key>.json with the change
(as rows before and after) and only the output lines that differed. It fails if an experiment changed nothing
and was not refused, so the site can never show an experiment that does not do what it says.

It also copies each pipeline's final database (from the normal run) to docs/data/db/<key>.sqlite for the
in-browser SQL console, after checking that no absolute path from this machine is stored in it.

    python tools/record_experiments.py [keys]
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lab"))
from civicworks_lab import server  # noqa: E402

OUT = ROOT / "docs" / "data"


def wait(*runs, timeout=300, may_fail=()) -> None:
    end = time.time() + timeout
    while any(r.status != "done" for r in runs) and time.time() < end:
        time.sleep(0.2)
    for r in runs:
        if r.status != "done" or (r.exit_code != 0 and r not in may_fail):
            raise RuntimeError(f"{r.id} did not finish cleanly (status {r.status}, exit {r.exit_code})")


def no_machine_paths(db: Path) -> None:
    con = sqlite3.connect(db)
    try:
        markers = [str(Path.home()), str(ROOT), ROOT.as_posix()]
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
            for row in con.execute(f'SELECT * FROM "{name}"'):
                for v in row:
                    if isinstance(v, str) and any(m.lower() in v.lower() for m in markers):
                        raise RuntimeError(f"{db.name}:{name} stores a path from this machine: {v[:80]}")
    finally:
        con.close()


def record(key: str) -> None:
    spec = server.CONTENT["experiments"].get(key, {})
    results = []
    server.BASELINES.pop(key, None)
    for exp in spec.get("experiments", []) + spec.get("safeguards", []):
        ids = server.start_experiment(key, exp["id"])
        normal, test = server.ACTIVE[ids["normal"]], server.ACTIVE[ids["experiment"]]
        wait(normal, test, may_fail=(test,) if exp.get("safeguard") else ())  # switching a safeguard off may crash it
        diff = server.compare_runs(normal, test)
        applied = test.applied or {}
        if not applied.get("error") and not any(d["kind"] in ("added", "removed") for d in diff):
            raise RuntimeError(f"{key}/{exp['id']} changed nothing - fix the experiment")
        leaked = [d["text"] for d in diff if any(m in d["text"] for m in (str(Path.home()), Path.home().as_posix()))]
        if leaked:
            raise RuntimeError(f"{key}/{exp['id']} output still shows a path from this machine: {leaked[0][:80]}")
        record = {k: exp.get(k) for k in ("id", "title", "plain", "predict", "look_for", "edits", "safeguard", "protects",
                                          "defend", "step")}
        results.append(record | {"refused": applied.get("error"), "rows": applied.get("rows", [])[:4], "diff": diff[:90],
                                 "exit": test.exit_code})
        print(f"  {key}/{exp['id']}: {'refused' if applied.get('error') else f'{len(diff)} lines differ'}")
    (OUT / "experiments").mkdir(parents=True, exist_ok=True)
    (OUT / "experiments" / f"{key}.json").write_text(json.dumps({"note": spec.get("note"),
                                                                 "experiments": [r for r in results if not r["safeguard"]],
                                                                 "safeguards": [r for r in results if r["safeguard"]]},
                                                                ensure_ascii=False), encoding="utf-8")
    # the final database of a normal run, for the in-browser SQL console
    base = server.BASELINES.get(key) or server.start_run(key, auto=True)
    wait(base)
    want = server.CONTENT["experiments"]["queries"][key]["db"]
    db = sorted(base.workspace.rglob(want), key=lambda p: len(p.parts))[0]
    (OUT / "db").mkdir(parents=True, exist_ok=True)
    target = OUT / "db" / f"{key}.sqlite"
    shutil.copyfile(db, target)
    con = sqlite3.connect(target)
    con.execute("VACUUM")
    con.close()
    no_machine_paths(target)
    print(f"  {key}: database {want} copied ({target.stat().st_size // 1024} KB)")


def main(keys: list[str]) -> int:
    for key in keys or list(server.PROJECTS):
        record(key)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
