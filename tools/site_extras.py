"""Site sections that need data recorded from real runs: experiments, the in-browser SQL console, the
role-by-role evidence page and the test count. Used by build_site.py."""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/data-dl/civicworks-automation-lab"
SQLJS = "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3"


def esc(s) -> str:
    return html.escape(str(s or ""))


def count_tests(project_dir: str) -> int:
    """Ask pytest how many tests a project has, so the site never shows a stale number."""
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT / project_dir,
                         capture_output=True, text=True, encoding="utf-8", check=False).stdout
    m = re.search(r"(\d+) tests? collected", out)
    return int(m.group(1)) if m else 0


# --- experiments ---------------------------------------------------------------------------------------
EXP_JS = """
<script>
(() => {
  const X = JSON.parse(document.getElementById('exp-data').textContent);
  const e = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const src = s => { const [f, t] = s.split('::'); return t ? `<code>${e(t)}</code> <span class="m">table in ${e(f)}</span>`
    : s.includes(' > ') ? `<code>${e(s.split(' > ')[1])}</code> <span class="m">sheet in ${e(s.split(' > ')[0])}</span>` : `<code>${e(s)}</code>`; };
  const grid = (cols, rows) => { const n = Math.min(10, Math.max(cols.length, ...rows.map(r => r.row.length)));
    return `<div class="rowgrid"><table><tr>${Array.from({length: n}, (_, i) => `<th>${e(cols[i])}</th>`).join('')}</tr>${rows.map(r =>
      `<tr class="${r.cls || ''}">${Array.from({length: n}, (_, i) => r.cells && i in r.cells ? `<td class="hit">${r.cells[i]}</td>` : `<td>${e(r.row[i])}</td>`).join('')}</tr>`).join('')}</table></div>`; };
  document.querySelectorAll('[data-exp]').forEach(btn => btn.onclick = () => {
    const x = X[+btn.dataset.exp], out = document.getElementById('expout' + btn.dataset.exp);
    const change = x.refused ? `<div class="ans refused"><b>The database refused the change:</b> <code>${e(x.refused)}</code>. Nothing was written,
        so the run carried on exactly as normal.</div>`
      : x.rows.map(r => `<h5>${src(r.source)}</h5>` + grid(r.cols, [...r.changed.map(c => ({row: c.row,
          cells: Object.fromEntries(c.cells.map(i => [i, `<s>${e(c.before[i])}</s> ${e(c.row[i])}`]))})),
          ...r.added.slice(0, 4).map(row => ({row, cls: 'addrow'})), ...r.removed.slice(0, 4).map(row => ({row, cls: 'delrow'}))])).join('');
    const diff = x.diff.length ? `<pre class="term diff">${x.diff.map(l => `<span class="${l.kind === 'heading' ? 'h' : l.kind === 'added' ? 'plus' : 'minus'}">${
        l.kind === 'added' ? '+ ' : l.kind === 'removed' ? '- ' : ''}${e(l.text)}</span>`).join('')}</pre>` : '<p class="m">The output was identical to the normal run.</p>';
    out.innerHTML = `<h4 class="rh">1. The change, in the data</h4>${change}
      <h4 class="rh">2. What the pipeline did differently</h4><p class="m"><b>+</b> lines appear only with the change; <b>-</b> lines only in the normal run.</p>${diff}
      <div class="ans"><b>What to notice:</b> ${e(x.look_for)}</div>`;
    btn.remove();
  });
})();
</script>"""


def experiments_section(key: str, bare: bool = False) -> str:
    f = DOCS / "data" / "experiments" / f"{key}.json"
    if not f.exists():
        return ""
    data = json.loads(f.read_text(encoding="utf-8"))
    xs = data["experiments"]
    if not xs:
        return (f"<section id='experiments'><span class='eyebrow'>What if?</span><h2>Experiments</h2>"
                f"<div class='panel'><p>{esc(data.get('note'))}</p></div></section>")
    cards = "".join(f"""<div class="panel exp"><span class="eyebrow">Experiment {n + 1}</span><h3>{esc(x['title'])}</h3>
      <p>{esc(x['plain'])}</p><div class="pred"><b>Predict first:</b> {esc(x['predict'])}</div>
      <div><button class="btn" data-exp="{n}">Show what the real pipeline did</button></div><div id="expout{n}"></div></div>"""
                    for n, x in enumerate(xs))
    payload = json.dumps(xs, ensure_ascii=False).replace("</", "<\\/")
    if bare:
        return f"{cards}<script type='application/json' id='exp-data'>{payload}</script>{EXP_JS}"
    return (f"<section id='experiments'><span class='eyebrow'>What if? - experiments on the real code</span>"
            f"<h2>Break the data on purpose and watch what happens</h2>"
            f"<p class='lede'>Each experiment changed one thing in the real input data and ran the real pipeline beside a normal run. "
            f"Below are only the lines of output the change made different. In the local Lab the same button runs it live, and you "
            f"can make your own changes.</p>{cards}<script type='application/json' id='exp-data'>{payload}</script>{EXP_JS}</section>")


# --- the SQL console, in the browser -----------------------------------------------------------------------
SQL_JS = """
<script>
(() => {
  const box = document.getElementById('sqlbox'); const Q = JSON.parse(document.getElementById('sql-data').textContent);
  const e = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  let db = null;
  const out = document.getElementById('sqlout'), info = document.getElementById('sqlinfo'), ta = document.getElementById('sqltext');
  async function open() {
    info.textContent = 'loading SQLite in your browser...';
    if (!window.initSqlJs) await new Promise((ok, no) => { const s = document.createElement('script'); s.src = '""" + SQLJS + """/sql-wasm.js';
      s.onload = ok; s.onerror = no; document.head.appendChild(s) });
    const SQL = await initSqlJs({ locateFile: f => '""" + SQLJS + """/' + f });
    const buf = await (await fetch(box.dataset.db)).arrayBuffer();
    db = new SQL.Database(new Uint8Array(buf));
    const tables = db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")[0].values.map(v => v[0]);
    document.getElementById('sqltables').innerHTML = 'Tables: ' + tables.map(t => `<button class="chip qbtn" data-t="${e(t)}">${e(t)}</button>`).join(' ');
    document.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { ta.value = `SELECT * FROM ${b.dataset.t} LIMIT 20;`; run() });
    document.getElementById('sqlopen').remove(); document.getElementById('sqlui').hidden = false;
  }
  function run() {
    try {
      const r = db.exec(ta.value);
      if (!r.length) { info.textContent = `${db.getRowsModified()} row(s) changed (in your browser's copy only)`; out.innerHTML = ''; return }
      const { columns, values } = r[r.length - 1];
      info.textContent = `${values.length} row(s)`;
      out.innerHTML = `<div class="rowgrid"><table><tr>${columns.map(c => `<th>${e(c)}</th>`).join('')}</tr>${values.slice(0, 200).map(v =>
        `<tr>${v.map(c => `<td>${e(c)}</td>`).join('')}</tr>`).join('')}</table></div>`;
    } catch (err) { info.textContent = ''; out.innerHTML = `<div class="ans refused"><b>The database said no:</b> <code>${e(err.message)}</code></div>` }
  }
  document.getElementById('sqlopen').onclick = () => open().then(() => { if (Q.length) { ta.value = Q[0].sql; teach(0); run() } })
    .catch(err => { info.textContent = 'Could not load SQLite: ' + err });
  const teach = i => { document.getElementById('teach').innerHTML = `<b>Teaches:</b> ${e(Q[i].teaches)}` };
  document.querySelectorAll('[data-q]').forEach(b => b.onclick = async () => { if (!db) await open(); ta.value = Q[+b.dataset.q].sql; teach(+b.dataset.q); run() });
  document.getElementById('sqlrun').onclick = run;
  ta.onkeydown = ev => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); run() } };
  document.getElementById('sqlreset').onclick = () => { db = null; location.reload() };
})();
</script>"""


def sql_section(key: str, queries: dict, bare: bool = False) -> str:
    q = queries.get(key)
    dbfile = DOCS / "data" / "db" / f"{key}.sqlite"
    if not q or not dbfile.exists():
        return ""
    kb = dbfile.stat().st_size // 1024
    chips = "".join(f'<button class="chip qbtn" data-q="{n}" title="{esc(x["teaches"])}">{esc(x["title"])}</button>'
                    for n, x in enumerate(q["list"]))
    payload = json.dumps(q["list"], ensure_ascii=False).replace("</", "<\\/")
    body = f"""<div class="panel sql" id="sqlbox" data-db="../data/db/{esc(key)}.sqlite">
    <div class="chips">{chips}</div>
    <div><button class="btn" id="sqlopen">Open the database</button></div>
    <div id="sqlui" hidden><p class="m" id="teach"></p><p class="m" id="sqltables"></p>
      <textarea id="sqltext" rows="8" spellcheck="false"></textarea>
      <div class="ctas"><button class="btn" id="sqlrun">Run (Ctrl+Enter)</button><button class="btn ghost" id="sqlreset">Reset the database</button></div></div>
    <p class="m" id="sqlinfo"></p><div id="sqlout"></div></div>
  <script type="application/json" id="sql-data">{payload}</script>{SQL_JS}"""
    if bare:
        return (f"<p class='m'>The real database a run of this pipeline left behind ({esc(q['db'])}, {kb} KB), opened in your browser - "
                f"nothing to install, nothing sent anywhere. Each example teaches one SQL idea; hover it to see which.</p>{body}")
    return f"""<section id="query"><span class="eyebrow">Query the data - in your browser</span><h2>Ask the pipeline's database a question</h2>
  <p class="lede">This is the real database a run of this pipeline left behind ({esc(q['db'])}, {kb} KB). It opens in your browser - nothing to
  install, nothing sent anywhere. Each example teaches one SQL idea; edit it or write your own. Changes stay in your browser's copy.</p>
  <div class="panel sql" id="sqlbox" data-db="../data/db/{esc(key)}.sqlite">
    <div class="chips">{chips}</div>
    <div><button class="btn" id="sqlopen">Open the database</button></div>
    <div id="sqlui" hidden><p class="m" id="teach"></p><p class="m" id="sqltables"></p>
      <textarea id="sqltext" rows="8" spellcheck="false"></textarea>
      <div class="ctas"><button class="btn" id="sqlrun">Run (Ctrl+Enter)</button><button class="btn ghost" id="sqlreset">Reset the database</button></div></div>
    <p class="m" id="sqlinfo"></p><div id="sqlout"></div></div>
  <script type="application/json" id="sql-data">{payload}</script>{SQL_JS}</section>"""


EXTRA_CSS = """
.subnav{position:sticky;top:57px;z-index:4;background:rgba(246,248,251,.95);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);
margin:-40px -24px 0;padding:8px 24px;display:flex;gap:6px;flex-wrap:wrap}.subnav a{font-size:13.5px;padding:4px 10px;border-radius:99px;
text-decoration:none;color:var(--muted);border:1px solid var(--line);background:var(--panel)}.subnav a:hover{color:var(--accent);border-color:var(--accent)}
section[id]{scroll-margin-top:110px}
.exp{gap:12px}.term.diff .plus{background:#e6eef7;display:block}.term.diff .minus{background:#f8e5e1;color:var(--muted);text-decoration:line-through;display:block}
.term.diff .h{font-weight:700;display:block;margin-top:6px}.ans.refused{background:#f8e5e1}
.sql textarea{width:100%;font:13.5px/1.55 var(--mono);padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#f9fbfd;color:var(--ink);resize:vertical}
.chip.qbtn{cursor:pointer;border:1px solid var(--line);background:var(--panel);font:inherit;font-size:13px}.chip.qbtn:hover{border-color:var(--accent);color:var(--accent)}
.m{color:var(--muted);font-size:14px}.tour{display:grid;gap:8px;margin:0;padding-left:22px}.role h2{font-size:21px}
.start{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.start a{background:var(--panel);border:1px solid var(--line);
border-radius:12px;padding:16px 18px;text-decoration:none;color:var(--ink);display:grid;gap:6px}.start a:hover{border-color:var(--accent)}
.start b{font-size:16px}.start span{color:var(--muted);font-size:14px}.start i{font:600 12px var(--mono);color:var(--accent);font-style:normal}
"""
