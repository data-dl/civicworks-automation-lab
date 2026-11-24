"""Build the GitHub Pages site in docs/ from learn/*.yaml, each project's migrations, the videos and the
rendered outputs. Usage: python tools/build_site.py"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_extras import EXTRA_CSS, count_tests, experiments_section, roles_page_body, sql_section  # noqa: E402
from video_scripts import SCRIPTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/data-dl/civicworks-automation-lab"
LEARN = ROOT / "learn"
QUERIES: dict = {}


def esc(s) -> str:
    return html.escape(str(s or ""))


def load() -> dict:
    pipelines = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (LEARN / "pipelines").glob("*.yaml")]
    pipelines.sort(key=lambda p: p["order"])
    stats = json.loads((DOCS / "videos" / "videos.json").read_text(encoding="utf-8")) \
        if (DOCS / "videos" / "videos.json").exists() else {}
    for p in pipelines:
        p["stats"] = stats.get(p["key"], {})
        p["tests"] = count_tests(p["dir"])
        p["images"] = sorted((DOCS / "img").glob(f"{p['key']}-*.png"))
        rules = ROOT / p["dir"] / p["key"] / "rules.yaml"
        p["rules"] = yaml.safe_load(rules.read_text(encoding="utf-8"))["rules"] if rules.exists() else []
        p["schema"] = schema(ROOT / p["dir"] / "db" / "migrations")
    return {"pipelines": pipelines, "stats": stats,
            "glossary": yaml.safe_load((LEARN / "glossary.yaml").read_text(encoding="utf-8"))["terms"],
            "ideas": yaml.safe_load((LEARN / "big_ideas.yaml").read_text(encoding="utf-8"))["ideas"],
            "interview": yaml.safe_load((LEARN / "interview.yaml").read_text(encoding="utf-8")),
            "queries": yaml.safe_load((LEARN / "experiments.yaml").read_text(encoding="utf-8"))["queries"],
            "lab_tests": count_tests("lab"), **counts()}


def counts() -> dict:
    x = yaml.safe_load((LEARN / "experiments.yaml").read_text(encoding="utf-8"))
    return {"n_exp": sum(len(v.get("experiments", [])) for k, v in x.items() if k != "queries"),
            "n_sql": sum(len(v["list"]) for v in x["queries"].values())}


def schema(folder: Path) -> list[dict]:
    """Apply the project's migrations to an empty in-memory database and read back the real structure."""
    if not folder.exists():
        return []
    con = sqlite3.connect(":memory:")
    for script in sorted(folder.glob("*.sql")):
        con.executescript(script.read_text(encoding="utf-8"))
    tables = []
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                               "AND name != 'schema_version' ORDER BY rowid"):
        cols = [{"name": c[1], "type": c[2] or "", "pk": bool(c[5]), "notnull": bool(c[3])}
                for c in con.execute(f'PRAGMA table_info("{name}")')]
        fks = {f[3]: f"{f[2]}.{f[4]}" for f in con.execute(f'PRAGMA foreign_key_list("{name}")')}
        uniques = []
        for idx in con.execute(f'PRAGMA index_list("{name}")'):
            if idx[2] and idx[3] != "pk":
                uniques.append([r[2] for r in con.execute(f'PRAGMA index_info("{idx[1]}")')])
        tables.append({"name": name, "columns": cols, "fks": fks, "uniques": uniques})
    triggers = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
    con.close()
    if triggers:
        tables[-1]["triggers"] = triggers
    return tables


CSS = """
:root{--bg:#f6f8fb;--panel:#fff;--ink:#1b2430;--muted:#5b6877;--line:#dde3ea;--soft:#eef2f7;--accent:#2f5d8a;
--accent-soft:#e6eef7;--ok:#2d6f57;--warn:#8a6214;--bad:#a8402f;--sans:"Inter","Segoe UI",system-ui,-apple-system,sans-serif;
--mono:"JetBrains Mono","Cascadia Mono",Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 var(--sans)}
a{color:var(--accent)}h1,h2,h3{line-height:1.2;text-wrap:balance;margin:0}p{margin:0}
.top{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1180px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;gap:22px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font-weight:650}
.brand i{width:32px;height:32px;border-radius:8px;background:var(--accent);color:#fff;display:grid;place-items:center;
font:700 12px var(--mono);font-style:normal}
.top nav{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}.top nav a{padding:6px 10px;border-radius:6px;text-decoration:none;
color:var(--muted);font-size:14.5px}.top nav a:hover,.top nav a.on{background:var(--accent-soft);color:var(--accent)}
main{max-width:1180px;margin:0 auto;padding:40px 24px 90px;display:grid;gap:56px}
section{display:grid;gap:18px;min-width:0}
.eyebrow{font:600 12px/1 var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--accent)}
.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:40px;align-items:center}
.hero h1{font-size:clamp(32px,4.4vw,50px);letter-spacing:-.02em;line-height:1.08}
.hero .lede{font-size:18.5px;color:var(--muted);max-width:60ch}
.lede{color:var(--muted);font-size:17px;max-width:72ch}
.ctas{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:9px;background:var(--accent);color:#fff;
text-decoration:none;font-weight:600;font-size:15px}.btn.ghost{background:var(--panel);color:var(--accent);border:1px solid var(--line)}
video{width:100%;border-radius:12px;background:#0e1520;aspect-ratio:16/9;box-shadow:0 14px 40px rgba(27,36,48,.14)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.stat b{display:block;font-size:30px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}.stat span{color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:grid;align-content:start;min-width:0}
a.card{text-decoration:none;color:var(--ink);transition:transform .15s,border-color .15s}a.card:hover{transform:translateY(-2px);border-color:var(--accent)}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;border-bottom:1px solid var(--line)}
.card .b{padding:14px 16px;display:grid;gap:6px}.card .n{font:600 12px var(--mono);color:var(--muted)}.card p{color:var(--muted);font-size:14.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{font-size:12.5px;padding:3px 9px;border-radius:99px;background:var(--accent-soft);color:var(--accent)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;display:grid;gap:10px;min-width:0}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;counter-reset:s}
.flow div{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:grid;gap:4px;position:relative}
.flow div::before{counter-increment:s;content:counter(s);font:600 12px var(--mono);color:var(--accent)}
.flow b{font-size:15px}.flow span{font-size:14px;color:var(--muted)}.flow small{font:12px var(--mono);color:var(--accent)}
table{border-collapse:collapse;width:100%;font-size:14.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;background:var(--soft)}.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
code{font:13.5px var(--mono);background:var(--soft);padding:1px 5px;border-radius:4px}
pre{font:13.5px/1.6 var(--mono);background:#f9fbfd;border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto;margin:0}
.erd{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.erd .t{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.erd h4{margin:0;padding:8px 12px;background:var(--accent-soft);color:var(--accent);font:600 14px var(--mono)}
.erd ul{list-style:none;margin:0;padding:8px 12px;font:12.8px/1.7 var(--mono)}.erd .pk{color:var(--accent);font-weight:700}
.erd .fk{color:var(--warn)}.erd em{font-style:normal;color:var(--muted)}
.gallery{display:grid;gap:22px}.gallery figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.gallery img{width:100%;display:block;max-height:640px;object-fit:contain;object-position:top;background:#fff}
.gallery figcaption{padding:10px 14px;color:var(--muted);font-size:14.5px;border-top:1px solid var(--line)}
.decision{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:0 10px 10px 0;padding:14px 18px;display:grid;gap:4px}
.decision .vs{color:var(--muted);font-size:14px}
.qa{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px;display:grid;gap:8px}
.qa b{font-size:15.5px}.qa p{background:var(--soft);padding:8px 12px;border-radius:7px;font-size:15px}
.qa small{display:block;font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.arch{display:grid;gap:14px}.arch .ops{background:var(--accent);color:#fff;border-radius:12px;padding:16px 20px;display:grid;gap:4px}
.arch .ops span{color:#dbe6f2;font-size:14.5px}.arch .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.arch .p{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:grid;gap:4px;text-decoration:none;color:var(--ink)}
.arch .p span{color:var(--muted);font-size:13.5px}
.matrix td,.matrix th{text-align:center}.matrix td:first-child,.matrix th:first-child{text-align:left}.dot{color:var(--accent);font-size:18px}
.gloss{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.gloss div{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.gloss b{display:block}
.gloss span{color:var(--muted);font-size:14.5px}.gloss i{display:block;font-style:normal;color:var(--accent);font-size:13.5px;margin-top:4px}
.stepnav{display:flex;flex-wrap:wrap;gap:6px}.stepnav button{width:34px;height:34px;border-radius:50%;border:1px solid var(--line);
background:var(--panel);color:var(--muted);font:600 13px var(--mono);cursor:pointer}.stepnav button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.pred{background:#f7eedb;border-radius:8px;padding:10px 14px}.ans{background:#e6eef7;border-radius:8px;padding:10px 14px}
.term{max-height:380px;white-space:pre-wrap}.term .bad{color:var(--bad)}.term .ok{color:var(--ok)}.term .warn{color:var(--warn)}
button.btn{border:none;cursor:pointer;font:inherit}button.btn.ghost{border:1px solid var(--line)}button:disabled{opacity:.4;cursor:default}
.deck{position:fixed;inset:0;background:var(--bg);display:grid;grid-template-rows:1fr auto}.slide{display:none;padding:6vh 8vw;align-content:center;gap:22px}
.slide.on{display:grid}.slide h1{font-size:clamp(34px,5vw,58px);letter-spacing:-.02em}.slide .lede{font-size:clamp(17px,1.6vw,21px)}
.deckbar{display:flex;justify-content:space-between;align-items:center;padding:12px 24px;border-top:1px solid var(--line);background:var(--panel);color:var(--muted)}
.rh{margin:14px 0 2px;font-size:16px}.stepper h5{margin:10px 0 4px;font-size:13.5px;font-weight:600}.stepper .m{color:var(--muted);font-size:13px;font-weight:400}
.rowgrid{overflow-x:auto;border:1px solid var(--line);border-radius:8px}.rowgrid table{border-collapse:collapse;width:100%;font:12px/1.4 var(--mono)}
.rowgrid th,.rowgrid td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis}
.rowgrid th{background:var(--soft,#eef2f7);color:var(--muted)}.rowgrid td.hit{background:#f7eedb;font-weight:600}.rowgrid td.hit s{color:var(--bad);font-weight:400}
.rowgrid mark{background:none;color:#8a6214;font-weight:700}.rowgrid tr.addrow td{background:#e9f0f7}.rowgrid tr.delrow td{color:var(--muted);text-decoration:line-through}
footer{border-top:1px solid var(--line);background:var(--panel)}footer .in{max-width:1180px;margin:0 auto;padding:22px 24px;color:var(--muted);font-size:14px;display:grid;gap:6px}
@media(max-width:860px){.hero,.two{grid-template-columns:1fr}.top .in{flex-wrap:wrap}}
"""


def page(title: str, body: str, depth: int = 0, nav: str = "") -> str:
    up = "../" * depth
    links = [("index.html", "Overview", "home"), ("index.html#pipelines", "Pipelines", "pipelines"),
             ("learn.html", "Concepts", "learn"), ("run.html", "Run it", "run"), ("roles.html", "For hiring teams", "roles"),
             (REPO, "GitHub", "gh")]
    navs = "".join(f'<a href="{h if h.startswith("http") else up + h}" class="{"on" if k == nav else ""}">{t}</a>'
                   for h, t, k in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="Eight tested data pipelines on invented data: validation, approvals, rollback, orchestration.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<link rel="stylesheet" href="{up}assets/site.css"></head><body>
<header class="top"><div class="in"><a class="brand" href="{up}index.html"><i>CW</i>CivicWorks Automation Lab</a><nav>{navs}</nav></div></header>
<main>{body}</main>
<footer><div class="in"><span>CivicWorks Automation Lab. Every organisation, person, place and number is invented. MIT licensed.</span>
<span>Built with AI coding assistance to the author's design; every behaviour described here is covered by a test that runs on every change.</span></div></footer>
</body></html>"""


def index(d: dict) -> str:
    ps = d["pipelines"]
    tests = sum(p["tests"] for p in ps)
    cards = "".join(f"""<a class="card" href="p/{p['key']}.html"><img src="videos/{p['key']}-poster.jpg" alt="" loading="lazy">
      <div class="b"><span class="n">{p['order']:02d}</span><h3>{esc(p['title'])}</h3><p>{esc(p['tagline'])}</p>
      <div class="chips">{''.join(f'<span class="chip">{esc(s)}</span>' for s in p['skills'][:3])}</div></div></a>""" for p in ps)
    ops = next(p for p in ps if p["key"] == "opspilot")
    others = [p for p in ps if p["key"] != "opspilot"]
    arch = f"""<div class="arch"><div class="ops"><b>{esc(ops['title'])}</b><span>{esc(ops['tagline'])}</span></div>
      <div class="row">{''.join(f'<a class="p" href="p/{p["key"]}.html"><b>{esc(p["title"])}</b><span>{esc(p["steps"][0]["name"])} &rarr; ... &rarr; {esc(p["steps"][-1]["name"])}</span></a>' for p in others)}</div></div>"""
    skills = [("Ingestion from several sources", {"atlas", "ledgerguard", "masterrecord", "reconcilehub", "regional"}),
              ("Schemas, keys and migrations", {p["key"] for p in ps}),
              ("Data-quality rules that block", {"atlas", "openbadge", "regional", "ledgerguard", "safesite"}),
              ("Human approval gates", {"atlas", "regional", "safesite", "masterrecord", "reconcilehub", "opspilot"}),
              ("Versioned outputs and rollback", {"atlas", "openbadge", "regional", "ledgerguard", "reconcilehub"}),
              ("Checkpoint and resume", {"atlas", "opspilot"}),
              ("Idempotent reruns", {"safesite", "masterrecord", "reconcilehub", "opspilot", "regional"}),
              ("Excel / Word / PDF / JSON outputs", {"atlas", "openbadge", "regional", "ledgerguard", "safesite", "masterrecord", "reconcilehub"}),
              ("Orchestration and safe agents", {"opspilot"})]
    matrix = "<tr><th>skill</th>" + "".join(f"<th>{esc(p['title'].split()[0])}</th>" for p in ps) + "</tr>" + "".join(
        f"<tr><td>{esc(s)}</td>" + "".join(f"<td>{'<span class=dot>&#9679;</span>' if p['key'] in keys else ''}</td>" for p in ps) + "</tr>"
        for s, keys in skills)
    ideas = "".join(f'<div class="panel"><span class="eyebrow">{n:02d}</span><h3>{esc(i["title"])}</h3><p class="lede" style="font-size:15.5px">{esc(i["plain"])}</p></div>'
                    for n, i in enumerate(d["ideas"], start=1))
    return page("CivicWorks Automation Lab", f"""
<section class="hero" id="overview"><div style="display:grid;gap:18px"><span class="eyebrow">Data engineering portfolio &middot; invented data</span>
  <h1>Reliable automation, from messy inputs to verified outputs.</h1>
  <p class="lede">Eight data pipelines for invented organisations. Each one takes data with planted problems, catches them,
  stops where a person has to decide, and leaves evidence of everything it did.</p>
  <div class="ctas"><a class="btn" href="#pipelines">See the pipelines</a><a class="btn ghost" href="run.html">Run them yourself</a><a class="btn ghost" href="slides.html">6 slides</a>
  <a class="btn ghost" href="{REPO}">Source on GitHub</a></div></div>
  <video controls preload="metadata" poster="videos/overview-poster.jpg" src="videos/overview.mp4"></video></section>
<section class="stats"><div class="stat"><b>8</b><span>pipelines, each a separate tested package</span></div>
  <div class="stat"><b>{tests}</b><span>automated tests (+{d['lab_tests']} for the Lab)</span></div><div class="stat"><b>2</b><span>operating systems in CI on every change</span></div>
  <div class="stat"><b>{d['n_exp']}</b><span>experiments on the real code</span></div><div class="stat"><b>{d['n_sql']}</b><span>SQL questions, in your browser</span></div></section>
<section><span class="eyebrow">Start here</span><h2>Four ways in, from two minutes to an afternoon</h2><div class="start">
  <a href="#overview"><i>2 minutes</i><b>Watch the overview</b><span>Narrated, replayed from real runs.</span></a>
  <a href="p/masterrecord.html#experiments"><i>5 minutes</i><b>Break the data, see what happens</b><span>Experiments on the real code: change one value, see only what it changed.</span></a>
  <a href="p/regional.html#query"><i>10 minutes</i><b>Query a pipeline's database</b><span>It opens in your browser. Joins, CTEs, window functions.</span></a>
  <a href="roles.html"><i>For hiring teams</i><b>What it shows, role by role</b><span>Data engineer, analytics engineer, data analyst - with links to the code.</span></a>
</div></section>
<section id="pipelines"><span class="eyebrow">The pipelines</span><h2>Each one shown running, with its real outputs</h2>
  <div class="grid">{cards}</div></section>
<section><span class="eyebrow">Architecture</span><h2>How it fits together</h2>
  <p class="lede">Each pipeline stands alone with its own data, rules and tests. OpsPilot runs them as one operation through a fixed list of
  allowed actions, waits for people before anything is published, and resumes from verified checkpoints.</p>{arch}</section>
<section><span class="eyebrow">Skills, with evidence</span><h2>Where each skill is shown</h2><div class="scroll"><table class="matrix">{matrix}</table></div></section>
<section><span class="eyebrow">Design principles</span><h2>Nine ideas behind all eight</h2><div class="grid">{ideas}</div>
  <p><a href="learn.html">Read them in depth, with the glossary &rarr;</a></p></section>
<section class="panel"><h3>How this was built</h3><p>{esc(d['interview']['about_ai']['plain'])}</p></section>
""", nav="home")


def erd(tables: list[dict]) -> str:
    out = []
    for t in tables:
        rows = []
        for c in t["columns"]:
            fk = t["fks"].get(c["name"])
            cls = "pk" if c["pk"] else ("fk" if fk else "")
            rows.append(f'<li class="{cls}">{esc(c["name"])} <em>{esc(c["type"].lower())}{" pk" if c["pk"] else ""}'
                        f'{" &rarr; " + esc(fk) if fk else ""}</em></li>')
        extra = "".join(f'<li><em>unique ({esc(", ".join(u))})</em></li>' for u in t["uniques"])
        extra += "".join(f'<li><em>trigger {esc(x)}</em></li>' for x in t.get("triggers", []))
        out.append(f'<div class="t"><h4>{esc(t["name"])}</h4><ul>{"".join(rows)}{extra}</ul></div>')
    return f'<div class="erd">{"".join(out)}</div>'


def captured_scenes(key: str) -> dict[int, dict]:
    """The real terminal output of the recorded run, split into scenes (from the video transcript)."""
    md = DOCS / "videos" / f"{key}.md"
    if not md.exists():
        return {}
    m = re.search(r"```\n(.*?)\n```", md.read_text(encoding="utf-8"), re.S)
    scenes: dict[int, dict] = {}
    for line in (m.group(1) if m else "").splitlines():
        h = re.match(r"^== (\d+)\. (.+)$", line.strip())
        if h:
            scenes[int(h.group(1))] = {"title": h.group(2), "lines": [line]}
        elif scenes:
            scenes[max(scenes)]["lines"].append(line)
    return scenes


STEP_JS = """
<script>
(() => {
  const data = JSON.parse(document.getElementById('steps-data').textContent);
  const box = document.getElementById('stepper'); let i = 0, shown = false;
  const cls = t => /\\b(BLOCKED|REFUSED|FAILED|QUARANTINED|STOPPED|rejected)\\b|\\[x\\]|!!/.test(t) ? 'bad'
    : /\\b(PUBLISHED|APPROVED|COMPLETE|FINAL|accepted|verified|OK)\\b/.test(t) ? 'ok' : /\\[-\\]|held|stale|awaiting/.test(t) ? 'warn' : '';
  const e = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const src = s => { const [f, t] = s.split('::'); return t ? `<code>${e(t)}</code> <span class="m">table in ${e(f)}</span>`
    : s.includes(' > ') ? `<code>${e(s.split(' > ')[1])}</code> <span class="m">sheet in ${e(s.split(' > ')[0])}</span>` : `<code>${e(s)}</code>`; };
  function grid(cols, rows) {
    const n = Math.min(10, Math.max(cols.length, ...rows.map(r => r.row.length)));
    return `<div class="rowgrid"><table><tr>${Array.from({length: n}, (_, i) => `<th>${e(cols[i] ?? '')}</th>`).join('')}</tr>${rows.map(r =>
      `<tr class="${r.cls || ''}">${Array.from({length: n}, (_, i) => r.cells && i in r.cells ? `<td class="hit">${r.cells[i]}</td>` : `<td>${e(r.row[i] ?? '')}</td>`).join('')}</tr>`).join('')}</table></div>`;
  }
  function rowsHtml(r) {
    if (!r || (!(r.traced || []).length && !(r.edits || []).length && !(r.fresh || []).length)) return '';
    let h = '';
    if (r.traced.length) h += `<h4 class="rh">Traced to the exact rows</h4><p class="m">Every record this scene's output names, found in the data.</p>` +
      r.traced.slice(0, 4).map(t => `<h5>${src(t.source)}</h5>` + grid(t.cols, t.rows.map(x => ({row: x.row,
        cells: Object.fromEntries(x.cells.map(i => [i, `<mark>${e(x.row[i])}</mark>`]))})))).join('');
    if (r.edits.length) h += `<h4 class="rh">Rows that changed</h4><p class="m">Changed cells show <s>before</s> and after; shaded rows were added, struck-through rows removed.</p>` +
      r.edits.slice(0, 4).map(c => `<h5>${src(c.source)} <span class="m">${[c.n_changed && c.n_changed + ' changed', c.n_added && c.n_added + ' added', c.n_removed && c.n_removed + ' removed'].filter(Boolean).join(', ')}</span></h5>` +
        grid(c.cols, [...c.changed.map(x => ({row: x.row, cells: Object.fromEntries(x.cells.map(i => [i, `<s>${e(x.before[i] ?? '')}</s> ${e(x.row[i] ?? '')}`]))})),
          ...c.added.slice(0, 6).map(row => ({row, cls: 'addrow'})), ...c.removed.slice(0, 6).map(row => ({row, cls: 'delrow'}))])).join('');
    if (r.fresh.length) h += `<p class="m"><b>New data written:</b> ${r.fresh.map(f => `${src(f.source)} (${f.rows} rows)`).join(', ')}</p>`;
    return h;
  }
  function draw() {
    const s = data[i];
    box.innerHTML = `<div class="stepnav">${data.map((x, n) => `<button class="${n === i ? 'on' : ''}" data-n="${n}">${n + 1}</button>`).join('')}</div>
      <h3>Scene ${i + 1} of ${data.length}: ${e(s.title)}</h3><p>${e(s.explain)}</p>
      <div class="pred"><b>Predict first:</b> ${e(s.predict)}</div>
      ${shown ? `<pre class="term">${s.lines.map(l => `<span class="${cls(l)}">${e(l)}</span>`).join('\\n')}</pre><div class="ans"><b>What happened:</b> ${e(s.answer)}</div>${rowsHtml(s.rows)}`
              : `<button class="btn" id="reveal">Show what the real run did</button>`}
      <div class="ctas"><button class="btn ghost" id="prev" ${i ? '' : 'disabled'}>Previous scene</button>
      <button class="btn ghost" id="next" ${i < data.length - 1 ? '' : 'disabled'}>Next scene</button></div>`;
    box.querySelectorAll('[data-n]').forEach(b => b.onclick = () => { i = +b.dataset.n; shown = false; draw() });
    const r = document.getElementById('reveal'); if (r) r.onclick = () => { shown = true; draw() };
    document.getElementById('prev').onclick = () => { i--; shown = false; draw() };
    document.getElementById('next').onclick = () => { i++; shown = false; draw() };
  }
  draw();
})();
</script>"""


def stepper(p: dict) -> str:
    captured = captured_scenes(p["key"])
    rows_file = DOCS / "data" / "rows" / f"{p['key']}.json"
    rows = json.loads(rows_file.read_text(encoding="utf-8")) if rows_file.exists() else {}
    data = [{"title": captured.get(n, {}).get("title", f"Scene {n}"), "lines": captured.get(n, {}).get("lines", []),
             "rows": rows.get(str(n), {}), **{k: s[k] for k in ("explain", "predict", "answer")}}
            for n, s in sorted(p["scenes"].items())]
    if not any(d["lines"] for d in data):
        return ""
    payload = json.dumps(data).replace("</", "<\\/")
    return (f"<section id='step'><span class='eyebrow'>Step through it - no install needed</span><h2>Predict, then see what the real run did</h2>"
            f"<p class='lede'>Every scene of the recorded run. Read what is about to happen, make a prediction, then reveal the actual "
            f"terminal output. To run it yourself one scene at a time, use the <a href='../run.html'>CivicWorks Lab</a>.</p>"
            f"<div class='panel stepper' id='stepper'></div><script type='application/json' id='steps-data'>"
            f"{payload}</script>{STEP_JS}</section>")


def pipeline_page(p: dict) -> str:
    imgs = list(zip(p["images"], [a[2] for a in SCRIPTS[p["key"]]["artifacts"]], strict=False))
    gallery = "".join(f'<figure><img src="../img/{img.name}" alt="{esc(cap)}" loading="lazy"><figcaption>{esc(cap)}</figcaption></figure>'
                      for img, cap in imgs)
    rules = ""
    if p["rules"]:
        rules = ("<section id='rules'><span class='eyebrow'>The rulebook</span><h2>Every check, why it exists, how to fix it</h2><div class='scroll'><table>"
                 "<tr><th>rule</th><th>severity</th><th>why</th><th>fix</th></tr>" +
                 "".join(f"<tr><td><code>{esc(r['id'])}</code></td><td>{esc(r['severity'])}</td><td>{esc(r['rationale'])}</td>"
                         f"<td>{esc(r['remediation'])}</td></tr>" for r in p["rules"]) + "</table></div></section>")
    code = f"{REPO}/tree/main/{p['dir']}"
    jumps = [("watch", "Watch"), ("step", "Step through"), ("experiments", "Experiments"), ("query", "Query the data"),
             ("rules", "Rules"), ("model", "Data model"), ("outputs", "Outputs"), ("why", "Why built this way"),
             ("questions", "Questions"), ("run", "Run it")]
    subnav = '<nav class="subnav">' + "".join(f'<a href="#{a}">{esc(b)}</a>' for a, b in jumps) + "</nav>"
    return page(p["title"], f"""{subnav}
<section class="hero" id="watch"><div style="display:grid;gap:16px"><span class="eyebrow">Pipeline {p['order']} of 8</span><h1>{esc(p['title'])}</h1>
  <p class="lede">{esc(p['tagline'])}</p><div class="chips">{''.join(f'<span class="chip">{esc(s)}</span>' for s in p['skills'])}</div>
  <div class="ctas"><a class="btn" href="{code}">Code and README</a><a class="btn ghost" href="../run.html">Run it</a></div>
  <p class="lede" style="font-size:15px">{p['tests']} automated tests. Video replayed from a real run ({p['stats'].get('real_run', '?')} s).</p></div>
  <video controls preload="metadata" poster="../videos/{p['key']}-poster.jpg" src="../videos/{p['key']}.mp4">
  <track kind="captions" src="../videos/{p['key']}.vtt" srclang="en" label="English" default></video></section>
<section class="two"><div class="panel"><span class="eyebrow">The problem, plainly</span><p>{esc(p['story'])}</p></div>
  <div class="panel"><span class="eyebrow">What it does, in one minute</span><p>{esc(p['one_minute'])}</p></div></section>
<section><span class="eyebrow">How it works</span><h2>Step by step</h2><div class="flow">{''.join(f"<div><b>{esc(s['name'])}</b><span>{esc(s['plain'])}</span><small>{esc(s['technical'])}</small></div>" for s in p['steps'])}</div></section>
<section class="two"><div class="panel"><span class="eyebrow">Inputs</span><table>{''.join(f"<tr><td><code>{esc(i['name'])}</code></td><td>{esc(i['what'])}</td></tr>" for i in p['inputs'])}</table></div>
  <div class="panel"><span class="eyebrow">Outputs</span><table>{''.join(f"<tr><td><code>{esc(o['name'])}</code></td><td>{esc(o['what'])}</td></tr>" for o in p['outputs'])}</table></div></section>
{stepper(p)}
{experiments_section(p['key'])}
{sql_section(p['key'], QUERIES)}
{rules}
<section id="model"><span class="eyebrow">Data model</span><h2>The database, read from its own migrations</h2>
  <p class="lede">Built by applying the project's numbered migration scripts to an empty database. Blue marks a primary key; amber arrows are
  foreign keys - links the database itself enforces.</p>{erd(p['schema'])}</section>
<section id="outputs"><span class="eyebrow">Real outputs</span><h2>What it produced in the recorded run</h2><div class="gallery">{gallery}</div></section>
<section id="why"><span class="eyebrow">Design decisions</span><h2>Why it is built this way</h2>{''.join(f"<div class='decision'><h3>{esc(x['choice'])}</h3><span class='vs'>instead of: {esc(x['instead_of'])}</span><p>{esc(x['why'])}</p></div>" for x in p['decisions'])}</section>
<section><span class="eyebrow">Failure handling</span><h2>What goes wrong, and what happens</h2><div class="scroll"><table><tr><th>situation</th><th>result</th></tr>
  {''.join(f"<tr><td>{esc(f['what'])}</td><td>{esc(f['result'])}</td></tr>" for f in p['failures'])}</table></div></section>
<section id="questions"><span class="eyebrow">Questions</span><h2>Questions it answers</h2>{''.join(f"<div class='qa'><b>{esc(q['q'])}</b><p><small>In short</small>{esc(q['simple'])}</p><p><small>In depth</small>{esc(q['technical'])}</p></div>" for q in p['questions'])}</section>
<section id="run"><span class="eyebrow">Run it</span><pre>python start.py              # one command: sets everything up and opens the Lab
cd {esc(p['dir'])}
python -m {esc(p['key'])} demo --out build/demo     # or run just this demo
python -m pytest                                       # and its tests</pre></section>
""", depth=1, nav="pipelines")


def learn_page(d: dict) -> str:
    ideas = "".join(f"<div class='panel'><span class='eyebrow'>{n:02d}</span><h3>{esc(i['title'])}</h3><p>{esc(i['plain'])}</p>"
                    f"<p style='color:var(--muted)'><b>Why:</b> {esc(i['why'])}</p><p style='color:var(--muted)'><b>Where:</b> {esc(i['where'])}</p></div>"
                    for n, i in enumerate(d["ideas"], start=1))
    gloss = "".join(f"<div id='{re.sub(r'[^a-z0-9]+', '-', k.lower())}'><b>{esc(k)}</b><span>{esc(v['plain'])}</span>"
                    + (f"<i>Like: {esc(v['like'])}</i>" if v.get("like") else "") + "</div>"
                    for k, v in sorted(d["glossary"].items(), key=lambda kv: kv[0].lower()))
    return page("Concepts - CivicWorks", f"""
<section><span class="eyebrow">From first principles</span><h1>The concepts, in plain language</h1>
<p class="lede">You do not need a computer-science background to follow these pipelines. Nine ideas explain why they are built the way they
are, and every technical word is defined below with an everyday comparison.</p></section>
<section><h2>Nine ideas behind all eight pipelines</h2><div class="grid">{ideas}</div></section>
<section><h2>Glossary</h2><div class="gloss">{gloss}</div></section>""", nav="learn")


def run_page(d: dict) -> str:
    dirs = " ".join(f'-e "./{p["dir"]}[dev]"' for p in d["pipelines"])
    rows = "".join(f"<tr><td>{esc(p['title'])}</td><td><code>cd {esc(p['dir'])} &amp;&amp; python -m {esc(p['key'])} demo</code></td></tr>"
                   for p in d["pipelines"])
    return page("Run it - CivicWorks", f"""
<section><span class="eyebrow">Try it</span><h1>Run the pipelines yourself</h1>
<p class="lede">Everything runs locally with Python 3.11 or newer. No accounts, no network, no real data. Each demo generates its own invented
data from a fixed seed, so you see exactly what the videos show.</p></section>
<section class="panel"><h2>One command</h2><p class="lede">With Python 3.11 or newer installed:</p>
<pre>git clone {REPO}
cd civicworks-automation-lab
python start.py</pre><p class="lede">It creates a private environment in <code>.venv</code>, installs the eight pipelines and the Lab, checks
that every demo runs, and opens the Lab in your browser. Run it again any time - it skips what is already done. On Windows you can also
double-click <code>Start CivicWorks Lab.cmd</code>.</p></section>
<section><h2>Or step by step</h2><pre>git clone {REPO}
cd civicworks-automation-lab
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install {dirs} -e ./lab</pre></section>
<section><h2>Run any demo</h2><p class="lede">Run each one from its own folder.</p><div class="scroll"><table><tr><th>pipeline</th><th>command</th></tr>{rows}</table></div></section>
<section><h2>The CivicWorks Lab: run it one scene at a time</h2>
<p class="lede">The Lab is a small local web app. Pick a pipeline and it runs the real demo one scene at a time: before each scene it explains what
is about to happen and asks you to predict the result; after it, it shows the output and the exact rows and cells that changed. Between
scenes you can change the data yourself - edit an input file or run SQL - and watch the pipeline react. Each pipeline also has one-click
experiments, a SQL console with example questions, and the concepts, glossary and interview flashcards.</p>
<pre>python -m civicworks_lab          # opens http://127.0.0.1:8870</pre></section>
<section><h2>Step mode without the Lab</h2><p class="lede">Any demo pauses before each scene if <code>CIVICWORKS_STEP=1</code> is set; press Enter to continue.</p>
<pre>CIVICWORKS_STEP=1 python -m atlas demo --out build/step</pre></section>
<section><h2>Tests</h2><pre>cd atlas-license-directory &amp;&amp; python -m pytest</pre><p class="lede">GitHub Actions runs lint, every project's tests and every
demo on Ubuntu and Windows after each push.</p></section>""", nav="run")


def deck(d: dict) -> str:
    ps = d["pipelines"]
    tests = sum(p["tests"] for p in ps)
    slides = [
        ("CivicWorks Automation Lab", "Reliable automation, from messy inputs to verified outputs.",
         "<p class='lede'>Eight data pipelines on invented data. Each catches planted problems, stops where a person must decide, "
         "and leaves evidence of everything it did.</p>"),
        ("The problem", "Published data multiplies every mistake.",
         "<p class='lede'>A wrong record in a report, a directory or a public file reaches everyone who uses it. Exports fail quietly. "
         "Two systems disagree. A rerun duplicates work. These pipelines are built so none of that happens silently.</p>"),
        ("What I built", "Eight pipelines, one standard.",
         "<div class='grid'>" + "".join(f"<div class='panel'><b>{esc(p['title'])}</b><span style='color:var(--muted);font-size:15px'>"
                                        f"{esc(p['tagline'])}</span></div>" for p in ps) + "</div>"),
        ("How they work", "Check, decide, release, keep evidence.",
         "<div class='grid'>" + "".join(f"<div class='panel'><b>{esc(i['title'])}</b></div>" for i in d["ideas"][2:8]) + "</div>"),
        ("Evidence", f"{tests} tests, two operating systems, every change.",
         "<p class='lede'>GitHub Actions installs all eight projects on fresh Ubuntu and Windows machines and runs every test and every "
         "demo after each push. Each run writes a manifest of input and output fingerprints. Every video is replayed from a real run.</p>"),
        ("See it", "Watch, step through, run it.",
         f"<p class='lede'>Overview video and per-pipeline walkthroughs: <a href='index.html'>the site</a>. On each pipeline page: a "
         f"step-by-step replay, experiments that break the data on purpose, and a SQL console on its real database. "
         f"Source: <a href='{REPO}'>{REPO.replace('https://', '')}</a>.</p>"),
    ]
    body = "".join(f"<section class='slide{' on' if n == 0 else ''}'><span class='eyebrow'>{n + 1} / {len(slides)} &middot; "
                   f"{esc(t)}</span><h1>{esc(h)}</h1>{b}</section>" for n, (t, h, b) in enumerate(slides))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CivicWorks - slides</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<link rel="stylesheet" href="assets/site.css"></head><body><div class="deck"><div>{body}</div>
<div class="deckbar"><a href="index.html">Back to the site</a><span id="pos"></span><span><button class="btn ghost" id="p">Previous</button>
<button class="btn" id="n">Next</button></span></div></div>
<script>const s=[...document.querySelectorAll('.slide')];let i=0;const go=k=>{{i=Math.max(0,Math.min(s.length-1,k));
s.forEach((x,n)=>x.classList.toggle('on',n===i));document.getElementById('pos').textContent=(i+1)+' of '+s.length}};
document.getElementById('p').onclick=()=>go(i-1);document.getElementById('n').onclick=()=>go(i+1);
addEventListener('keydown',e=>{{if(['ArrowRight','PageDown',' '].includes(e.key))go(i+1);if(['ArrowLeft','PageUp'].includes(e.key))go(i-1)}});go(0);</script>
</body></html>"""


def main() -> None:
    d = load()
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "p").mkdir(exist_ok=True)
    global QUERIES
    QUERIES = d["queries"]
    (DOCS / "assets" / "site.css").write_text(CSS.strip() + "\n" + EXTRA_CSS.strip() + "\n", encoding="utf-8")
    tests = sum(p["tests"] for p in d["pipelines"])
    (DOCS / "roles.html").write_text(page("For hiring teams - CivicWorks", roles_page_body(d, tests), nav="roles"),
                                     encoding="utf-8")
    (DOCS / "index.html").write_text(index(d), encoding="utf-8")
    (DOCS / "learn.html").write_text(learn_page(d), encoding="utf-8")
    (DOCS / "run.html").write_text(run_page(d), encoding="utf-8")
    (DOCS / "slides.html").write_text(deck(d), encoding="utf-8")
    for p in d["pipelines"]:
        (DOCS / "p" / f"{p['key']}.html").write_text(pipeline_page(p), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"site: {len(d['pipelines'])} pipeline pages, {sum(p['tests'] for p in d['pipelines'])} tests counted")


if __name__ == "__main__":
    main()
