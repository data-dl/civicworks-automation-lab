"""Row-level change tracking for a run's workspace.

Between two moments of a run, which rows of which tables and CSV files were added, removed or changed -
and in a changed row, exactly which cells. Plus tracing: for each record identifier a scene's output
names (EQ-0010, HV-NF01, T-007 ...), the exact rows that hold it, so a reported problem can be followed
back to the input row that caused it.

Used by the Lab while a run is paused, and by tools/build_site.py to record the same view for the site.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

MAX_ROWS = 5000          # a table bigger than this is tracked by count only
SHOW = 12                # rows shown per category per source
ID_TOKEN = re.compile(r"(?<![\w-])(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{3,}(?![\w-])")
NOT_IDS = re.compile(r"^(\d{4}Q\d|SHA-\d+|\d{4}-\d\d(-\d\d)?|UTF-\d+|ISO-\d+|H\d+|V\d+)$")


def _cell(v) -> str:
    return "" if v is None else str(v)


def _sqlite_sources(ws: Path, db: Path, out: dict) -> None:
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                           "'sqlite_%' ORDER BY name")]
        for name in names:
            info = list(con.execute(f'PRAGMA table_info("{name}")'))
            cols = [c[1] for c in info]
            pk = [i for _, i in sorted((c[5], n) for n, c in enumerate(info) if c[5])]
            if con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] > MAX_ROWS:
                continue
            rows = {}
            if pk:
                for r in con.execute(f'SELECT * FROM "{name}"'):
                    vals = [_cell(v) for v in r]
                    rows[json.dumps([vals[i] for i in pk])] = vals
            else:
                try:
                    for r in con.execute(f'SELECT rowid, * FROM "{name}"'):
                        rows[str(r[0])] = [_cell(v) for v in r[1:]]
                except sqlite3.Error:
                    for r in con.execute(f'SELECT * FROM "{name}"'):
                        vals = [_cell(v) for v in r]
                        rows[json.dumps(vals)] = vals
            out[f"{db.relative_to(ws).as_posix()}::{name}"] = {"cols": cols, "rows": rows}
    except sqlite3.Error:
        pass
    finally:
        con.close()


def _csv_source(ws: Path, path: Path, out: dict) -> None:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            data = list(csv.reader(f))
    except (OSError, UnicodeDecodeError, csv.Error):
        return
    if not data or len(data) > MAX_ROWS:
        return
    cols, body = data[0], data[1:]
    first = [r[0] if r else "" for r in body]
    keyed = all(first) and len(set(first)) == len(first)
    rows = {}
    for r in body:
        rows[r[0] if keyed else json.dumps(r)] = r
    out[path.relative_to(ws).as_posix()] = {"cols": cols, "rows": rows}


def _xlsx_sources(ws: Path, path: Path, out: dict) -> None:
    try:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True)
    except Exception:  # noqa: BLE001 - a half-written or locked workbook is simply skipped
        return
    try:
        for sheet in wb.worksheets:
            data = [[_cell(v) for v in r] for r in sheet.iter_rows(values_only=True)]
            data = [r for r in data if any(r)]
            if not data or len(data) > MAX_ROWS:
                continue
            cols, body = data[0], data[1:]
            first = [r[0] for r in body]
            keyed = all(first) and len(set(first)) == len(first)
            out[f"{path.relative_to(ws).as_posix()} > {sheet.title}"] = {
                "cols": cols, "rows": {(r[0] if keyed else json.dumps(r)): r for r in body}}
    finally:
        wb.close()


def contents(ws: Path) -> dict:
    """Every SQLite table and CSV file in the workspace, as {source: {cols, rows: {key: values}}}."""
    out: dict = {}
    if not ws.exists():
        return out
    for db in sorted(ws.rglob("*.sqlite"))[:12]:
        _sqlite_sources(ws, db, out)
    for path in sorted(ws.rglob("*.csv"))[:40]:
        _csv_source(ws, path, out)
    for path in sorted(p for p in ws.rglob("*.xlsx") if not p.name.startswith("~$"))[:12]:
        _xlsx_sources(ws, path, out)
    # Some tables store absolute paths (archives, restores). Show them relative to the run, as the terminal does,
    # so no machine's folder names leak into what is displayed or published.
    roots = sorted({str(ws), str(ws.resolve()), ws.as_posix(), ws.resolve().as_posix()}, key=len, reverse=True)
    for src in out.values():
        for k, row in src["rows"].items():
            if any(r in v for v in row for r in roots):
                src["rows"][k] = [_mask(v, roots) for v in row]
    return out


def _mask(value: str, roots: list[str]) -> str:
    for r in roots:
        value = value.replace(r, "<workspace>")
    return value


def changes(before: dict, after: dict) -> list[dict]:
    """Per source: rows added, removed and changed (with the changed cell positions)."""
    result = []
    for source, a in after.items():
        b = before.get(source, {"cols": a["cols"], "rows": {}})
        added = [k for k in a["rows"] if k not in b["rows"]]
        removed = [k for k in b["rows"] if k not in a["rows"]]
        changed = []
        for k, row in a["rows"].items():
            old = b["rows"].get(k)
            if old is not None and old != row:
                cells = [i for i in range(max(len(row), len(old)))
                         if (row[i] if i < len(row) else None) != (old[i] if i < len(old) else None)]
                changed.append({"row": row, "before": old, "cells": cells})
        if added or removed or changed:
            result.append({"source": source, "cols": a["cols"], "new_source": source not in before,
                           "added": [a["rows"][k] for k in added[:SHOW]], "n_added": len(added),
                           "removed": [b["rows"][k] for k in removed[:SHOW]], "n_removed": len(removed),
                           "changed": changed[:SHOW], "n_changed": len(changed)})
    for source in before:
        if source not in after:
            b = before[source]
            result.append({"source": source, "cols": b["cols"], "new_source": False, "added": [], "n_added": 0,
                           "removed": list(b["rows"].values())[:SHOW], "n_removed": len(b["rows"]),
                           "changed": [], "n_changed": 0})
    # changed rows first: they are the interesting ones; then added, then removed
    result.sort(key=lambda c: (-c["n_changed"], c["new_source"], -c["n_added"]))
    return result


def identifiers(text: str) -> list[str]:
    seen = []
    for t in ID_TOKEN.findall(text):
        if not NOT_IDS.match(t) and t not in seen:
            seen.append(t)
    return seen


def trace(after: dict, text: str, limit: int = 10) -> list[dict]:
    """The rows that hold each identifier the scene's output names - the exact records behind a finding.

    A token found in more than three rows of a source is a shared value (a period, a class), not a record
    identifier, so it is not traced there.
    """
    tokens = identifiers(text)
    if not tokens:
        return []
    pats = {t: re.compile(rf"(?<![\w-]){re.escape(t)}(?![\w-])") for t in tokens}
    found = []
    # inputs (CSV) first: the point is to see the source row that caused a finding
    for source in sorted(after, key=lambda s: ("::" in s, s)):
        src = after[source]
        hits: dict[str, list] = {}
        for row in src["rows"].values():
            for t, pat in pats.items():
                cells = [i for i, v in enumerate(row) if v == t or pat.search(v)]
                if cells:
                    hits.setdefault(t, []).append({"row": row, "cells": cells})
        rows = [dict(h, token=t) for t, hs in hits.items() if len(hs) <= 3 for h in hs]
        if rows:
            found.append({"source": source, "cols": src["cols"], "rows": rows[:SHOW]})
        if len(found) >= limit:
            break
    return found
