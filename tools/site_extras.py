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


def experiments_section(key: str) -> str:
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


def sql_section(key: str, queries: dict) -> str:
    q = queries.get(key)
    dbfile = DOCS / "data" / "db" / f"{key}.sqlite"
    if not q or not dbfile.exists():
        return ""
    kb = dbfile.stat().st_size // 1024
    chips = "".join(f'<button class="chip qbtn" data-q="{n}" title="{esc(x["teaches"])}">{esc(x["title"])}</button>'
                    for n, x in enumerate(q["list"]))
    payload = json.dumps(q["list"], ensure_ascii=False).replace("</", "<\\/")
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


# --- for hiring teams ------------------------------------------------------------------------------------
def roles_page_body(d: dict, tests: int) -> str:
    def link(path: str, text: str) -> str:
        return f'<a href="{REPO}/blob/main/{path}">{esc(text)}</a>'

    roles = [
        ("Data engineer", "Pipelines that are safe to run twice, resume after a crash, and never publish half a result.", [
            ("Idempotent loads and reruns", "A second run changes nothing: decisions, writes and releases are keyed so they cannot repeat.",
             link("reconcilehub/reconcilehub/commit.py", "reconcilehub/commit.py")),
            ("Atomic publish and rollback", "Outputs are built in staging, verified, then swapped in with one rename; rollback re-hashes first.",
             link("atlas-license-directory/atlas/release.py", "atlas/release.py")),
            ("Checkpoint and resume", "An interrupted run skips only the steps whose outputs still hash the same.",
             link("opspilot-control-center/opspilot/executor.py", "opspilot/executor.py")),
            ("Schema migrations", "Numbered SQL migrations with keys, foreign keys, unique indexes and append-only triggers.",
             link("opspilot-control-center/db/migrations/001_init.sql", "opspilot migrations")),
            ("CI on two operating systems", f"{tests} tests, lint and every demo on Ubuntu and Windows on every push.",
             link(".github/workflows/tests.yml", "tests.yml")),
        ]),
        ("Analytics engineer", "Data models people can trust: tested rules, documented columns, and SQL that answers real questions.", [
            ("Data-quality rules as data", "A rule registry with severity, rationale and remediation; blocking rules stop a release and name the record.",
             link("atlas-license-directory/atlas/rules.yaml", "atlas/rules.yaml")),
            ("Data dictionaries", "Every table and column documented next to the code.",
             link("masterrecord-steward/docs/data_dictionary.md", "masterrecord data dictionary")),
            ("Field-level precedence", "Which source wins for which field, written as configuration and held for a person when no rule decides.",
             link("masterrecord-steward/masterrecord/precedence.yaml", "precedence.yaml")),
            ("SQL you can run", f"{d['n_sql']} example questions across the eight databases: joins, CTEs, window functions, anti-joins, date math.",
             '<a href="p/regional.html#query">the in-browser SQL console</a>'),
            ("Tests that pin behaviour", "Each pipeline's tests name the behaviour they protect.",
             link("openbadge-registry-publisher/tests/test_openbadge.py", "test_openbadge.py")),
        ]),
        ("Data analyst", "Reports that reconcile to the source, explain changes, and refuse to go out incomplete.", [
            ("Excel reports with live formulas", "Quarterly packs whose totals are formulas, with charts, approved only when every venue is in.",
             '<a href="p/regional.html">Regional Programs Analytics</a>'),
            ("Reconciling numbers", "Category parts must add up to the reported total; a mismatch names the venue.",
             '<a href="p/regional.html#experiments">the totals experiment</a>'),
            ("Period-over-period change", "LAG() over a CTE: each venue's change since last quarter.",
             '<a href="p/regional.html#query">try the query</a>'),
            ("Word reports for two audiences", "A board summary and a detailed report from the same checked data.",
             '<a href="p/safesite.html">SafeSite Compliance Cycle</a>'),
            ("Exception workbooks", "Daily QA exceptions as a workbook people can filter, with the reason for each row.",
             '<a href="p/ledgerguard.html">LedgerGuard Data Quality</a>'),
        ]),
    ]
    blocks = "".join(f"""<section class="panel role"><span class="eyebrow">{esc(name)}</span><h2>{esc(lead)}</h2>
      <div class="scroll"><table><tr><th>skill</th><th>what it shows</th><th>where to look</th></tr>{''.join(
        f'<tr><td><b>{esc(s)}</b></td><td>{esc(w)}</td><td>{where}</td></tr>' for s, w, where in rows)}</table></div></section>"""
                     for name, lead, rows in roles)
    story = d["interview"]["stories"][0]
    return f"""
<section><span class="eyebrow">For hiring teams</span><h1>What this portfolio shows, role by role</h1>
<p class="lede">Each row points to the exact file or page where a skill is demonstrated. Everything runs on invented data; every behaviour
described is covered by a test that runs on every change.</p>
<div class="stats"><div class="stat"><b>8</b><span>pipelines, separate packages</span></div><div class="stat"><b>{tests}</b><span>automated tests</span></div>
<div class="stat"><b>{d['n_exp']}</b><span>experiments on the real code</span></div><div class="stat"><b>{d['n_sql']}</b><span>SQL questions to run in the browser</span></div></div></section>
<section class="panel"><span class="eyebrow">Five minutes</span><h2>The quickest way to judge it</h2><ol class="tour">
<li><a href="index.html#overview">Watch the two-minute overview</a>.</li>
<li>Open <a href="p/masterrecord.html#experiments">MasterRecord's experiments</a> and press <b>Show what the real pipeline did</b>: one changed value in a feed becomes exactly one changed cell in the Excel master.</li>
<li>Run a query in <a href="p/regional.html#query">Regional's SQL console</a> - the database opens in your browser.</li>
<li>Read <a href="{REPO}/blob/main/openbadge-registry-publisher/openbadge/registry.py">one real fix</a>: an experiment showed a badge with an unknown type silently vanished because of an inner join; it now blocks the release, with a test.</li>
<li>Skim the <a href="{REPO}">repository</a> and its green CI badge.</li></ol></section>
{blocks}
<section class="panel"><span class="eyebrow">A story to ask about</span><h2>{esc(story['title'])}</h2>
<p><b>Situation.</b> {esc(story['situation'])}</p><p><b>Problem.</b> {esc(story['problem'])}</p><p><b>What I did.</b> {esc(story['action'])}</p>
<p><b>Result.</b> {esc(story['result'])}</p></section>"""


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
