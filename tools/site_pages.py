"""The website's main pages, built around one idea: show a little, let people open more.

Home: what this proves and three ways in. Pipeline: the flow first (click a step; switch a safeguard off), then
"watch it run", "try it" and "go deeper" as sections you open when you want them. Hiring: what each role's hiring
manager expects, and where it is shown.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/data-dl/civicworks-automation-lab"
HIRING = yaml.safe_load((ROOT / "learn" / "hiring.yaml").read_text(encoding="utf-8"))


def esc(s) -> str:
    return html.escape(str(s or ""))


def layer(title: str, hint: str, body: str, open_: bool = False) -> str:
    """A section you open when you want it - the main way the site avoids being overwhelming."""
    return (f"<details class='layer'{' open' if open_ else ''}><summary><b>{esc(title)}</b><span>{esc(hint)}</span></summary>"
            f"<div class='layer-body'>{body}</div></details>")


def recorded_switches(key: str) -> dict:
    f = DOCS / "data" / "experiments" / f"{key}.json"
    if not f.exists():
        return {}
    return {s["safeguard"]: {k: s.get(k) for k in ("diff", "exit", "look_for", "defend")}
            for s in json.loads(f.read_text(encoding="utf-8")).get("safeguards", [])}


def flow_section(key: str, flow: dict) -> str:
    data = json.dumps({"flow": flow, "recorded": recorded_switches(key)}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<section id="flow"><span class="eyebrow">How it works - click any step</span>
  <h2>The flow, step by step</h2>
  <div id="flowbox"></div>
  <script type="application/json" id="flow-data">{data}</script>
  <script src="../assets/flow.js"></script>
  <script>
  (() => {{
    const d = JSON.parse(document.getElementById('flow-data').textContent);
    const f = renderFlow(document.getElementById('flowbox'), d.flow, {{ repo: "{REPO}",
      runSwitch: async node => d.recorded[node.safeguard] }});
    if (location.hash === '#switch' && f.first >= 0) f.show(f.first);
  }})();
  </script></section>"""


def pipeline_page(p: dict, flow: dict, parts: dict) -> str:
    """parts: html for stepper, experiments, sql, rules, erd, gallery (built by build_site)."""
    n_exp = parts["n_exp"]
    watch = f"""<div class="two"><video controls preload="metadata" poster="../videos/{p['key']}-poster.jpg" src="../videos/{p['key']}.mp4">
      <track kind="captions" src="../videos/{p['key']}.vtt" srclang="en" label="English" default></video>
      <div class="panel"><span class="eyebrow">In one minute</span><p>{esc(p['one_minute'])}</p>
      <p class="m">Narrated, replayed from a real run ({p['stats'].get('real_run', '?')} s of computing).</p></div></div>
      {layer("Step through the run, scene by scene", "Predict each scene, then reveal what the real run printed and which rows changed", parts['stepper'])}"""
    tryit = "".join([
        layer(f"Break the data on purpose ({n_exp})" if n_exp else "Break the data on purpose",
              "Change one thing in the input and see only what the pipeline did differently", parts["experiments"]) if parts["experiments"] else "",
        layer("Query the data with SQL", "The pipeline's real database opens in your browser, with example questions", parts["sql"]) if parts["sql"] else "",
    ])
    deeper = "".join([
        layer("Why it is built this way", f"{len(p['decisions'])} design decisions and what was chosen instead",
              "".join(f"<div class='decision'><h3>{esc(x['choice'])}</h3><span class='vs'>instead of: {esc(x['instead_of'])}</span><p>{esc(x['why'])}</p></div>"
                      for x in p["decisions"])),
        layer("What goes wrong, and what happens", f"{len(p['failures'])} situations",
              "<div class='scroll'><table><tr><th>situation</th><th>what the pipeline does</th></tr>"
              + "".join(f"<tr><td>{esc(f['what'])}</td><td>{esc(f['result'])}</td></tr>" for f in p["failures"]) + "</table></div>"),
        layer("The rulebook", f"{len(p['rules'])} rules, each with its reason and fix", parts["rules"]) if p["rules"] else "",
        layer("The data model", "Tables, keys and links, read from the project's own migrations", parts["erd"]),
        layer("What it produced", "Real outputs from the recorded run: PDFs, Excel, Word, JSON", f"<div class='gallery'>{parts['gallery']}</div>"),
        layer("Questions it answers", f"{len(p['questions'])} questions, a short answer and a deeper one",
              "".join(f"<div class='qa'><b>{esc(q['q'])}</b><p><small>In short</small>{esc(q['simple'])}</p><p><small>In depth</small>{esc(q['technical'])}</p></div>"
                      for q in p["questions"])),
        layer("Run it yourself", "One command sets everything up",
              f"<pre>python start.py                                   # sets up and opens the CivicWorks Lab\n"
              f"cd {esc(p['dir'])} &amp;&amp; python -m {esc(p['key'])} demo   # or just this demo\n"
              f"python -m pytest                                  # its {p['tests']} tests</pre>"),
    ])
    jumps = [("flow", "The flow"), ("watch", "Watch it run"), ("try", "Try it"), ("deeper", "Go deeper")]
    return f"""<nav class="subnav">{''.join(f'<a href="#{a}">{b}</a>' for a, b in jumps)}</nav>
<section class="phead"><span class="eyebrow">Pipeline {p['order']} of 8</span><h1>{esc(p['title'])}</h1>
  <p class="lede">{esc(p['tagline'])}</p>
  <div class="panel story"><span class="eyebrow">The problem it solves</span><p>{esc(p['story'])}</p>
  <div class="chips">{''.join(f'<span class="chip">{esc(s)}</span>' for s in p['skills'])}</div></div></section>
{flow_section(p['key'], flow)}
<section id="watch"><span class="eyebrow">Watch it run</span><h2>See it work</h2>{watch}</section>
<section id="try"><span class="eyebrow">Try it - nothing to install</span><h2>Experiment with it</h2>
  <p class="lede">The safeguard switch is in the flow above. These go further: change the data, or ask its database a question.</p>{tryit}</section>
<section id="deeper"><span class="eyebrow">Go deeper</span><h2>For the detail</h2>{deeper}
  <p class="m"><a href="{REPO}/tree/main/{p['dir']}">The code and README on GitHub</a></p></section>"""


def index_page(d: dict, tests: int) -> str:
    ps = d["pipelines"]
    cards = "".join(f"""<a class="card" href="p/{p['key']}.html#flow"><img src="videos/{p['key']}-poster.jpg" alt="" loading="lazy">
      <div class="b"><span class="n">{p['order']:02d}</span><h3>{esc(p['title'])}</h3><p>{esc(p['tagline'])}</p>
      <span class="go">Explore the flow &rarr;</span></div></a>""" for p in ps)
    ops = next(p for p in ps if p["key"] == "opspilot")
    others = [p for p in ps if p["key"] != "opspilot"]
    arch = f"""<div class="arch"><div class="ops"><b>{esc(ops['title'])}</b><span>{esc(ops['tagline'])}</span></div>
      <div class="row">{''.join(f'<a class="p" href="p/{p["key"]}.html#flow"><b>{esc(p["title"])}</b><span>{esc(p["tagline"])}</span></a>' for p in others)}</div></div>"""
    ideas = "".join(f'<div class="panel"><span class="eyebrow">{n:02d}</span><h3>{esc(i["title"])}</h3><p class="m">{esc(i["plain"])}</p></div>'
                    for n, i in enumerate(d["ideas"], start=1))
    return f"""
<section class="hero" id="overview"><div style="display:grid;gap:18px"><span class="eyebrow">Data portfolio &middot; invented data, real code</span>
  <h1>Data pipelines that catch bad data before anyone sees it.</h1>
  <p class="lede">{esc(HIRING['value'])}</p>
  <div class="ctas"><a class="btn" href="p/masterrecord.html#flow">Explore a pipeline</a><a class="btn ghost" href="hiring.html">For hiring managers</a>
  <a class="btn ghost" href="{REPO}">The code on GitHub</a></div></div>
  <div style="display:grid;gap:8px"><video controls preload="metadata" poster="videos/overview-poster.jpg" src="videos/overview.mp4"></video>
  <span class="m">Two-minute narrated overview, replayed from real runs.</span></div></section>
<section class="stats"><div class="stat"><b>8</b><span>pipelines, each its own tested package</span></div>
  <div class="stat"><b>{tests}</b><span>automated tests, run on Linux and Windows on every change</span></div>
  <div class="stat"><b>8</b><span>safeguards you can switch off to see why they exist</span></div>
  <div class="stat"><b>3</b><span>real bugs found by experimenting, each fixed with a test</span></div></section>
<section><span class="eyebrow">Three ways in</span><div class="start">
  <a href="p/masterrecord.html#flow"><i>5 minutes</i><b>Click through a pipeline</b><span>Each step in plain words, with its real code and the database rule behind it.</span></a>
  <a href="p/openbadge.html#switch"><i>2 minutes</i><b>Remove a safeguard</b><span>Switch one protection off and see exactly what goes wrong without it.</span></a>
  <a href="hiring.html"><i>For hiring managers</i><b>What it shows, role by role</b><span>Data analyst, analytics engineer, data engineer - and where each skill is shown.</span></a>
</div></section>
<section id="pipelines"><span class="eyebrow">The eight pipelines</span><h2>Each one turns a real kind of data work into something you can run</h2>
  <div class="grid">{cards}</div></section>
<section><span class="eyebrow">How they fit together</span><h2>Seven pipelines and one operator</h2>
  <p class="lede">Each pipeline stands alone with its own data, rules and tests. OpsPilot runs them as one operation: it can prepare
  anything, but anything that publishes waits for a person.</p>{arch}</section>
<section>{layer("The nine ideas behind all eight", "The principles an interviewer will probe - in plain language", f"<div class='grid'>{ideas}</div><p><a href='learn.html'>Read them in depth, with a glossary &rarr;</a></p>")}
  {layer("How this was built", "Including the honest answer about AI", f"<p>{esc(HIRING['about_ai'])}</p>")}</section>"""


def hiring_page(tests: int) -> str:
    roles = "".join(f"""<section class="panel role"><span class="eyebrow">{esc(r['role'])}</span><h2>{esc(r['they_want'])}</h2>
      <div class="scroll"><table><tr><th>What they expect you to know</th><th>What it means</th><th>Where it is shown</th></tr>{''.join(
        f"<tr><td><b>{esc(x['skill'])}</b></td><td>{esc(x['means'])}</td><td><a href='{esc(x['where']['href'])}'>{esc(x['where']['label'])}</a></td></tr>"
        for x in r['expect'])}</table></div></section>""" for r in HIRING["roles"])
    return f"""
<section><span class="eyebrow">For hiring managers and recruiters</span><h1>What this portfolio shows</h1>
<p class="lede">{esc(HIRING['value'])}</p>
<div class="stats"><div class="stat"><b>8</b><span>pipelines</span></div><div class="stat"><b>{tests}</b><span>automated tests</span></div>
<div class="stat"><b>2</b><span>operating systems in CI, plus a from-scratch install, on every change</span></div>
<div class="stat"><b>0</b><span>real people or records - everything is invented</span></div></div></section>
<section class="panel"><span class="eyebrow">Five minutes</span><h2>The quickest way to judge it</h2><ol class="tour">
<li><a href="index.html#overview">Watch the two-minute overview</a>.</li>
<li>On <a href="p/openbadge.html#switch">OpenBadge</a>, switch off the check after upload: a cut-off file goes live and the next release crashes reading it.</li>
<li>Click through <a href="p/masterrecord.html#flow">MasterRecord's flow</a>: each step's code, and the database rule behind it, explained.</li>
<li>Run a query in <a href="p/regional.html#try">Regional's SQL console</a>; the database opens in your browser.</li>
<li>Skim the <a href="{REPO}">repository</a> and its CI.</li></ol></section>
{roles}
<section class="panel"><span class="eyebrow">Found by experimenting</span><h2>Testing the pipelines against their own experiments found real bugs</h2>
<p>A badge with an unknown type vanished silently from a public release because of an inner join - it now blocks the release and names
the badge. A person's name that drifted under the same member id passed unreported - it is now noted for review. A report step crashed when
a quarter was never approved. Each is fixed, with a test that keeps it fixed.</p></section>"""


CSS = """
.phead{display:grid;gap:14px}.phead h1{font-size:clamp(30px,4vw,44px);letter-spacing:-.02em}.story p{max-width:80ch}
.layer{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.layer>summary{cursor:pointer;list-style:none;padding:14px 18px;display:grid;gap:2px;position:relative;padding-right:44px}
.layer>summary::-webkit-details-marker{display:none}.layer>summary::after{content:"+";position:absolute;right:18px;top:12px;font:600 20px var(--mono);color:var(--accent)}
.layer[open]>summary::after{content:"\\2212"}.layer>summary b{font-size:16.5px}.layer>summary span{color:var(--muted);font-size:14px}
.layer[open]>summary{border-bottom:1px solid var(--line);background:var(--soft)}.layer-body{padding:16px 18px;display:grid;gap:14px;min-width:0}
.layer-body>.panel{border:none;padding:0}section>.layer+.layer{margin-top:-6px}
.card .go{font-size:14px;font-weight:600;color:var(--accent)}
"""
