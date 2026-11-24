"""Experiments: change a pipeline's real input data part-way through a run, then let the real code react.

An experiment is a list of edits applied to the run's workspace while it is paused (by default right after
scene 1, when the inputs have been written and nothing has read them yet):

    {csv: <glob>, where: {column: value}, set: {column: value}}     edit matching rows of a CSV file
    {csv: <glob>, where: {column: value}, delete: true}              delete matching rows
    {file: <glob>, delete: true}                                     delete a whole file
    {sqlite: <glob>, sql: "UPDATE ..."}                              run one statement on a run database

Every edit must hit something; an edit that matches nothing is an error, not a silent no-op, so an
experiment can never "pass" because it changed nothing.

Two runs of the same demo produce the same data (fixed seed, fixed dates), so a normal run and an
experiment run can be compared line by line: `compare()` returns only what the change made different.
"""

from __future__ import annotations

import csv
import difflib
import re
import sqlite3
from pathlib import Path


class ExperimentError(ValueError):
    pass


def _one(ws: Path, pattern: str) -> Path:
    hits = sorted(p for p in ws.glob(pattern) if p.is_file())
    if not hits:
        raise ExperimentError(f"no file matches {pattern}")
    path = hits[0].resolve()
    if ws.resolve() not in path.parents:
        raise ExperimentError("edits are confined to the run's workspace")
    return path


def _edit_csv(ws: Path, e: dict) -> str:
    path = _one(ws, e["csv"])
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols, rows = list(reader.fieldnames or []), list(reader)
    where = e.get("where", {})
    unknown = [c for c in [*where, *e.get("set", {})] if c not in cols]
    if unknown:
        raise ExperimentError(f"{path.name} has no column {', '.join(unknown)}")
    hit = [r for r in rows if all(r.get(k) == str(v) for k, v in where.items())]
    if not hit:
        raise ExperimentError(f"no row in {path.name} where {where}")
    if e.get("delete"):
        rows = [r for r in rows if r not in hit]
        what = f"deleted {len(hit)} row(s) from {path.name} where " + ", ".join(f"{k} = {v}" for k, v in where.items())
    else:
        for r in hit:
            r.update({k: str(v) for k, v in e["set"].items()})
        what = (f"{path.name}: " + ", ".join(f"{k} = {v}" for k, v in where.items()) + " -> "
                + ", ".join(f"{k} set to {v!r}" for k, v in e["set"].items()))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return what


def _edit_sqlite(ws: Path, e: dict) -> str:
    path = _one(ws, e["sqlite"])
    con = sqlite3.connect(path)
    try:
        before = con.total_changes
        con.executescript(e["sql"])          # may hold a PRAGMA first, e.g. to switch on foreign keys
        changed = con.total_changes - before
        if changed < 1:
            raise ExperimentError(f"the statement changed no rows in {path.name}")
        return f"{path.name}: {e['sql']}  ({changed} row(s))"
    finally:
        con.close()


def apply(ws: Path, edits: list[dict]) -> list[str]:
    done = []
    for e in edits:
        if "csv" in e:
            done.append(_edit_csv(ws, e))
        elif "sqlite" in e:
            done.append(_edit_sqlite(ws, e))
        elif "file" in e and e.get("delete"):
            path = _one(ws, e["file"])
            path.unlink()
            done.append(f"deleted the file {path.relative_to(ws.resolve()).as_posix()}")
        else:
            raise ExperimentError(f"unknown edit {e}")
    return done


_NOISE = [(re.compile(r"\b[0-9a-f]{10,64}\b"), "<hash>"),
          (re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?(\.\d+)?(Z|[+-]\d\d:\d\d)?"), "<time>"),
          (re.compile(r"\b\d{8}T\d{6}\b"), "<time>"),
          (re.compile(r"\b\d+(\.\d+)?s\b"), "<secs>")]


def _norm(line: str) -> str:
    for pat, rep in _NOISE:
        line = pat.sub(rep, line)
    return line


def compare(normal: list[dict], changed: list[dict]) -> list[dict]:
    """Line-level differences between a normal run and an experiment run, with scene headings for context.

    Returns [{scene, kind: 'same'|'added'|'removed'|'heading', text}], collapsing unchanged stretches.
    """
    a, b = [x["text"] for x in normal], [x["text"] for x in changed]
    scene_of = [x["scene"] for x in changed]
    ops = difflib.SequenceMatcher(a=[_norm(x) for x in a], b=[_norm(x) for x in b], autojunk=False).get_opcodes()
    out: list[dict] = []
    last_heading = None
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for j in range(j1, j2):
                if b[j].startswith("== "):
                    last_heading = {"scene": scene_of[j], "kind": "heading", "text": b[j]}
            continue
        if last_heading and (not out or out[-1] is not last_heading) and last_heading not in out:
            out.append(last_heading)
        for i in range(i1, i2):
            out.append({"scene": None, "kind": "removed", "text": a[i]})
        for j in range(j1, j2):
            kind = "heading" if b[j].startswith("== ") else "added"
            out.append({"scene": scene_of[j], "kind": kind, "text": b[j]})
            if kind == "heading":
                last_heading = out[-1]
    return out
