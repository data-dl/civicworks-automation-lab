"""Read learn/flows.yaml and attach the real code and SQL each step uses, straight from the repository.

Used by the Lab and by tools/build_site.py. Fails loudly if a referenced function or database object no longer
exists, so the explanations cannot silently drift away from the code.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # the repository
DIRS = {"atlas": "atlas-license-directory", "openbadge": "openbadge-registry-publisher",
        "regional": "regional-programs-analytics", "ledgerguard": "ledgerguard-data-quality",
        "safesite": "safesite-compliance-cycle", "masterrecord": "masterrecord-steward",
        "reconcilehub": "reconcilehub", "opspilot": "opspilot-control-center"}


def _function_source(path: Path, symbol: str) -> tuple[list[str], int]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parts = symbol.split(".")
    body = tree.body
    node = None
    for part in parts:
        node = next((n for n in body if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                     and n.name == part), None)
        if node is None:
            raise LookupError(f"{path.name}: no {symbol}")
        body = node.body
    lines = source.splitlines()[node.lineno - 1:node.end_lineno]
    return lines, node.lineno


def code_for(key: str, ref: dict) -> dict:
    path = ROOT / DIRS[key] / ref["file"]
    lines, start = _function_source(path, ref["symbol"])
    offset = 0
    if ref.get("focus"):
        offset = next((i for i, x in enumerate(lines) if ref["focus"] in x), None)
        if offset is None:
            raise LookupError(f"{ref['file']}:{ref['symbol']}: no line contains {ref['focus']!r}")
    shown = lines[offset:offset + ref.get("lines", 30)]
    indent = min((len(x) - len(x.lstrip()) for x in shown if x.strip()), default=0)
    return {"file": f"{DIRS[key]}/{ref['file']}", "line": start + offset, "symbol": ref["symbol"],
            "text": "\n".join(x[indent:] for x in shown).rstrip(), "more": offset + len(shown) < len(lines)}


def sql_for(key: str, name: str) -> str:
    con = sqlite3.connect(":memory:")
    for script in sorted((ROOT / DIRS[key] / "db" / "migrations").glob("*.sql")):
        con.executescript(script.read_text(encoding="utf-8"))
    rows = [r[0] for r in con.execute("SELECT sql FROM sqlite_master WHERE (name = ? OR (tbl_name = ? AND "
                                      "type = 'index')) AND sql IS NOT NULL ORDER BY type DESC", (name, name))]
    con.close()
    if not rows:
        raise LookupError(f"{key}: no table, index or trigger called {name}")
    return ";\n\n".join(rows) + ";"


def load() -> dict:
    flows = yaml.safe_load((ROOT / "learn" / "flows.yaml").read_text(encoding="utf-8"))
    guards = yaml.safe_load((ROOT / "learn" / "safeguards.yaml").read_text(encoding="utf-8"))
    for key, flow in flows.items():
        by_guard = {g["safeguard"]: g for g in guards.get(key, [])}
        for node in flow["nodes"]:
            if node.get("code"):
                node["source"] = code_for(key, node["code"])
            if node.get("sql"):
                node["sql"]["text"] = sql_for(key, node["sql"]["object"])
            if node.get("safeguard"):
                node["switch"] = by_guard[node["safeguard"]]
    return flows


if __name__ == "__main__":
    data = load()
    for key, flow in data.items():
        print(key, [(n["id"], n["source"]["line"] if n.get("source") else None) for n in flow["nodes"]])
