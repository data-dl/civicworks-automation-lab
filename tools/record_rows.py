"""Record each pipeline's row-level changes, scene by scene, for the site's step-throughs.

Runs every demo in step mode through the Lab's own machinery (the same code the Lab shows live) and writes
docs/data/rows/<key>.json: per scene, the rows each named record was traced to, and the rows that changed.

    python tools/record_rows.py [keys]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lab"))
from civicworks_lab import server  # noqa: E402

OUT = ROOT / "docs" / "data" / "rows"


def wait(run, timeout=180) -> None:
    end = time.time() + timeout
    while run.status == "running" and time.time() < end:
        time.sleep(0.1)


def slim(change: dict) -> dict:
    edits = [r for r in change.get("rows", []) if r["n_changed"] or (not r["new_source"] and (r["n_added"] or r["n_removed"]))]
    fresh = [{"source": r["source"], "rows": r["n_added"]} for r in change.get("rows", []) if r["new_source"]]
    return {"traced": change.get("traced", [])[:5], "edits": edits[:5], "fresh": fresh[:12]}


def record(key: str) -> dict:
    run = server.start_run(key)
    try:
        wait(run)
        while True:
            if run.status == "done":
                break
            server.next_scene(run)
            time.sleep(0.2)
            wait(run)
        if run.exit_code != 0:
            raise RuntimeError(f"{key} demo exited {run.exit_code}")
        return {str(n): slim(c) for n, c in sorted(run.changes.items()) if n}
    finally:
        if run.proc.poll() is None:
            run.proc.kill()


def main(keys: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for key in keys or list(server.PROJECTS):
        scenes = record(key)
        (OUT / f"{key}.json").write_text(json.dumps(scenes, ensure_ascii=False, separators=(",", ":")) + "\n",
                                         encoding="utf-8")
        print(f"{key}: {len(scenes)} scenes, {sum(len(s['traced']) + len(s['edits']) for s in scenes.values())} row views")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
