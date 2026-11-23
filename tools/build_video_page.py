"""Build the page that plays all six walkthrough videos, with each project's summary, the scene list and the
captured terminal output. Usage: python tools/build_video_page.py <output.html>  (videos expected in ./videos/)"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_scripts import SCRIPTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "videos"


def cues(key: str) -> list[tuple[str, str]]:
    text = (VIDEOS / f"{key}.vtt").read_text(encoding="utf-8")
    out = []
    for block in text.split("\n\n")[1:]:
        lines = block.strip().splitlines()
        if len(lines) >= 2:
            out.append((lines[0].split(" --> ")[0][3:8], " ".join(lines[1:])))
    return out


def terminal(key: str) -> str:
    md = (VIDEOS / f"{key}.md").read_text(encoding="utf-8")
    match = re.search(r"```\n(.*?)\n```", md, re.S)
    return match.group(1) if match else ""


def main(out: Path) -> None:
    stats = json.loads((VIDEOS / "videos.json").read_text(encoding="utf-8"))
    total_tests = sum(int(s["tests"].split()[0]) for s in stats.values())
    minutes = sum(s["seconds"] for s in stats.values()) / 60
    cards = []
    for key, spec in SCRIPTS.items():
        s = stats[key]
        scene_list = "".join(f"<li><span class='t'>{t}</span> {html.escape(c)}</li>" for t, c in cues(key))
        bullets = "".join(f"<li>{html.escape(b)}</li>" for b in spec["close"])
        cards.append(f"""
<article class="card" id="{key}">
  <div class="player"><video controls preload="metadata" poster="videos/{key}-poster.jpg" src="videos/{key}.mp4"></video></div>
  <div class="text">
    <h2>{html.escape(spec['title'])}</h2>
    <p class="problem">{html.escape(spec['problem'])}</p>
    <p class="facts"><span>{s['seconds']} s video</span><span>real run {s['real_run']} s</span><span>{s['tests']}</span></p>
    <ul class="showed">{bullets}</ul>
    <details><summary>Scene by scene</summary><ol class="scenes">{scene_list}</ol></details>
    <details><summary>Captured terminal output</summary><pre>{html.escape(terminal(key))}</pre></details>
  </div>
</article>""")
    page = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CivicWorks Videos</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: one column of project cards, each a 16:9 player beside its summary; stacks on phones. */
:root {{ --bg:#f4f6f8; --sheet:#ffffff; --ink:#1d2733; --muted:#5a6878; --rule:#d9e0e7; --accent:#1f6f8b;
  --code:#f3f6f9; --sans:"Segoe UI",system-ui,-apple-system,sans-serif; --mono:"Cascadia Mono",Consolas,monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#151b22; --sheet:#1c242d; --ink:#e4eaf0;
  --muted:#9aa8b6; --rule:#2f3a46; --accent:#6cc0dd; --code:#222c36; color-scheme:dark }} }}
:root[data-theme="dark"] {{ --bg:#151b22; --sheet:#1c242d; --ink:#e4eaf0; --muted:#9aa8b6; --rule:#2f3a46;
  --accent:#6cc0dd; --code:#222c36; color-scheme:dark }}
body {{ background:var(--bg); color:var(--ink); font:16px/1.55 var(--sans); margin:0 }}
.wrap {{ max-width:1180px; margin:0 auto; padding-block:28px 56px; padding-left:max(16px, env(safe-area-inset-left, 0px));
  padding-right:max(16px, env(safe-area-inset-right, 0px)); display:grid; gap:22px }}
header {{ display:grid; gap:8px }}
.eyebrow {{ font:600 12px/1 var(--mono); letter-spacing:.08em; text-transform:uppercase; color:var(--accent) }}
h1 {{ margin:0; font-size:30px; text-wrap:balance }}
.lede {{ margin:0; color:var(--muted); max-width:72ch }}
.stats {{ display:flex; flex-wrap:wrap; gap:8px 20px; font-variant-numeric:tabular-nums; color:var(--muted); font-size:14px }}
.stats b {{ color:var(--ink); font-size:18px }}
nav {{ display:flex; flex-wrap:wrap; gap:6px 14px; font-size:14px }}
nav a, a {{ color:var(--accent) }}
.card {{ background:var(--sheet); border:1px solid var(--rule); border-radius:8px; padding:16px; display:grid;
  grid-template-columns:minmax(0, 1.35fr) minmax(0, 1fr); gap:18px; align-items:start }}
.player video {{ width:100%; aspect-ratio:16/9; border-radius:6px; background:#000; display:block }}
.text {{ min-width:0; display:grid; gap:8px }}
h2 {{ margin:0; font-size:21px }}
.problem {{ margin:0 }}
.facts {{ margin:0; display:flex; flex-wrap:wrap; gap:6px; font-size:13px }}
.facts span {{ border:1px solid var(--rule); border-radius:4px; padding:1px 7px; color:var(--muted) }}
.showed {{ margin:0; padding-left:1.1em; display:grid; gap:2px; font-size:15px }}
details {{ border-top:1px solid var(--rule); padding-top:6px }}
summary {{ cursor:pointer; color:var(--accent); font-size:14px }}
.scenes {{ margin:8px 0 0; padding-left:0; list-style:none; display:grid; gap:6px; font-size:14px }}
.scenes .t {{ font:12px var(--mono); color:var(--muted); margin-right:6px }}
pre {{ margin:8px 0 0; background:var(--code); border-radius:6px; padding:10px; font:12px/1.45 var(--mono);
  overflow-x:auto; max-height:340px }}
footer {{ color:var(--muted); font-size:13px; max-width:80ch }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px }}
@media (max-width:820px) {{ .card {{ grid-template-columns:minmax(0, 1fr) }} }}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">CivicWorks Automation Lab</div>
  <h1>Six pipelines, each shown running</h1>
  <p class="lede">Each video replays a real run of the project's demo command, captured line by line, then shows the
  files it produced, rendered from the real outputs. Captions explain each scene. Every organisation, person and number
  is invented.</p>
  <div class="stats"><span><b>6</b> pipelines</span><span><b>{total_tests}</b> tests passing</span>
  <span><b>{minutes:.0f}</b> minutes of video</span></div>
  <nav>{''.join(f'<a href="#{k}">{html.escape(v["title"])}</a>' for k, v in SCRIPTS.items())}</nav>
</header>
{''.join(cards)}
<footer>Built with AI coding assistance to the author's design; nothing is claimed without a test. Videos made by
<code>tools/make_videos.py</code> from real runs on synthetic data.</footer>
</div>
"""
    out.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
