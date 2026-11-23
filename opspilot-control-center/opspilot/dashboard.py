"""A read-only status page built from the database: runs, steps, approvals and the event log.
It is a static file - opening it can change nothing."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .executor import OpsPilot
from .runkit import SYNTHETIC_NOTICE, atomic_write_text

COLOURS = {"done": "#1e7a46", "complete": "#1e7a46", "awaiting-approval": "#8a5a00", "blocked": "#a8322d",
           "failed": "#a8322d", "interrupted": "#5a4a9c", "skipped": "#5a6878", "running": "#1f6f8b"}


def _pill(text: str) -> str:
    colour = COLOURS.get(text, "#5a6878")
    return f'<span class="pill" style="color:{colour};border-color:{colour}">{html.escape(text)}</span>'


def build(ops: OpsPilot) -> Path:
    con = ops.con
    runs = con.execute("SELECT * FROM execution ORDER BY started_at, run_id").fetchall()
    parts = []
    for r in runs:
        steps = con.execute("SELECT s.stage_id, s.tool, s.effect_class, c.status, c.exit_code, c.artifact_hash, "
                            "a.authorization_id, a.role FROM stage s LEFT JOIN checkpoint c ON c.run_id = ? AND "
                            "c.stage_id = s.stage_id LEFT JOIN authorization a ON a.run_id = ? AND a.stage_id = "
                            "s.stage_id WHERE s.pipeline_id = ? ORDER BY s.ordinal",
                            (r["run_id"], r["run_id"], r["pipeline_id"])).fetchall()
        rows = "".join(
            f"<tr><td>{html.escape(s['stage_id'])}</td><td><code>{html.escape(s['tool'])}</code></td>"
            f"<td>{s['effect_class']}</td><td>{_pill(s['status'] or 'not reached')}</td>"
            f"<td>{'' if s['exit_code'] is None else s['exit_code']}</td>"
            f"<td><code>{(s['artifact_hash'] or '')[:12]}</code></td>"
            f"<td>{html.escape((s['authorization_id'] or '') + (' ' + s['role'] if s['role'] else ''))}</td></tr>"
            for s in steps)
        parts.append(f"<section><h2>{html.escape(r['run_id'])} {_pill(r['state'])}</h2>"
                     f"<p class='meta'>goal {html.escape(r['pipeline_id'])} - started {r['started_at']} - "
                     f"updated {r['updated_at']}</p><div class='scroll'><table><tr><th>step</th><th>tool</th>"
                     f"<th>effect</th><th>status</th><th>exit</th><th>output hash</th><th>approval</th></tr>{rows}"
                     "</table></div></section>")
    events = con.execute("SELECT * FROM event_log ORDER BY event_id DESC LIMIT 40").fetchall()
    ev = "".join(f"<tr><td>{e['event_id']}</td><td>{e['at'][11:19]}</td><td>{html.escape(e['run_id'] or '-')}</td>"
                 f"<td>{_pill(e['event_type'])}</td><td><code>{html.escape(json.dumps(json.loads(e['payload']))[:160])}"
                 "</code></td></tr>" for e in events)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>OpsPilot status</title><style>
body{{font:15px/1.5 system-ui,Segoe UI,sans-serif;background:#f6f8fa;color:#1d2733;margin:0;padding:24px 16px}}
main{{max-width:1100px;margin:0 auto}} h1{{margin:0 0 4px}} .meta{{color:#5a6878;margin:0 0 8px}}
section{{background:#fff;border:1px solid #d9e0e7;border-radius:6px;padding:12px 16px;margin:16px 0}}
.scroll{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #e6ebf0;vertical-align:top}}
th{{color:#5a6878;font-weight:600}} .pill{{border:1px solid;border-radius:3px;padding:1px 6px;font-size:12px}}
code{{font-family:Consolas,monospace;font-size:12px}}</style></head><body><main>
<h1>OpsPilot status</h1><p class="meta">Read-only snapshot - {html.escape(SYNTHETIC_NOTICE)}</p>
{''.join(parts)}<section><h2>Event log (newest first, append-only)</h2><div class="scroll"><table>
<tr><th>#</th><th>time</th><th>run</th><th>event</th><th>detail</th></tr>{ev}</table></div></section></main></body></html>
"""
    return atomic_write_text(ops.root / "status.html", page)
