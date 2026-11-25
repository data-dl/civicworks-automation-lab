"""The CivicWorks Lab: a local web app for running the eight pipelines step by step and studying them.

It serves one page and a small JSON API on 127.0.0.1 only. A guided run starts a project's real demo
command in step mode (CIVICWORKS_STEP=1), streams its output, and pauses between scenes; while paused,
the Lab inspects the run's workspace - new and changed files, database tables and row counts - and can
preview any output: CSV, JSON, Markdown, email drafts, Excel (formulas shown), Word, PDF pages and SQLite.

Only the registered demo commands can be started, and file access is confined to the Lab's own run folders.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from . import experiments, flows, rowdiff

ROOT = Path(__file__).resolve().parents[2]          # the repository
LEARN = ROOT / "learn"
STATIC = Path(__file__).with_name("static")
RUNS = ROOT / "build" / "lab-runs"
# Private interview prep lives OUTSIDE the repository, so it never reaches GitHub: a folder named
# civicworks-prep next to the repository, or wherever CIVICWORKS_PREP points.
PREP = Path(os.environ.get("CIVICWORKS_PREP") or ROOT.parent / "civicworks-prep")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PREVIEW_ROWS = 80


def load_content() -> dict:
    pipelines = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((LEARN / "pipelines").glob("*.yaml"))]
    pipelines.sort(key=lambda p: p["order"])
    videos = ROOT / "docs" / "videos"
    for p in pipelines:
        p["video"] = f"/videos/{p['key']}.mp4" if (videos / f"{p['key']}.mp4").exists() else None
        rules = ROOT / p["dir"] / p["key"] / "rules.yaml"
        if rules.exists():
            p["rules"] = yaml.safe_load(rules.read_text(encoding="utf-8"))["rules"]
    return {"pipelines": pipelines,
            "glossary": yaml.safe_load((LEARN / "glossary.yaml").read_text(encoding="utf-8"))["terms"],
            "ideas": yaml.safe_load((LEARN / "big_ideas.yaml").read_text(encoding="utf-8"))["ideas"],
            "hiring": yaml.safe_load((LEARN / "hiring.yaml").read_text(encoding="utf-8")),
            "flows": flows.load(),
            "experiments": _experiments(),
            "prep": load_prep()}


def load_prep() -> dict | None:
    """Your private prep - interview notes, role questions, work-mapping hints - if this computer has it."""
    if not (PREP / "interview.yaml").exists():
        return None
    prep = {"interview": yaml.safe_load((PREP / "interview.yaml").read_text(encoding="utf-8"))}
    if (PREP / "questions.yaml").exists():
        prep.update(yaml.safe_load((PREP / "questions.yaml").read_text(encoding="utf-8")))
    prep["folder"] = str(PREP)
    return prep


def read_notes() -> dict:
    f = PREP / "my-notes.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_note(key: str, text: str) -> None:
    if not PREP.exists():
        raise ValueError("no private prep folder on this computer")
    notes = read_notes()
    notes[key] = text[:20000]
    tmp = PREP / "my-notes.json.writing"
    tmp.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, PREP / "my-notes.json")


def _experiments() -> dict:
    """Experiments (data changes) and safeguard switches, per pipeline, plus the SQL questions."""
    x = yaml.safe_load((LEARN / "experiments.yaml").read_text(encoding="utf-8"))
    guards = yaml.safe_load((LEARN / "safeguards.yaml").read_text(encoding="utf-8"))
    for key, items in guards.items():
        x.setdefault(key, {"experiments": []})["safeguards"] = items
    return x


CONTENT = load_content()
PROJECTS = {p["key"]: p["dir"] for p in CONTENT["pipelines"]}


@dataclass
class Run:
    id: str
    key: str
    workspace: Path
    proc: subprocess.Popen
    lines: list[dict] = field(default_factory=list)
    status: str = "running"            # running | paused | done
    scene: int = 0
    exit_code: int | None = None
    started: float = field(default_factory=time.time)
    snapshots: list[dict] = field(default_factory=list)   # per pause: files and table counts
    changes: dict = field(default_factory=dict)            # scene number -> what changed during it
    experiment: dict | None = None                         # edits to apply while paused, see experiments.py
    auto: bool = False                                     # run straight through without waiting for a person
    applied: dict | None = None                            # what the experiment changed


RUN_LOCK = threading.Lock()
ACTIVE: dict[str, Run] = {}


def snapshot(ws: Path) -> dict:
    files, tables = {}, {}
    if ws.exists():
        for p in ws.rglob("*"):
            if p.is_file() and ".writing" not in p.name:
                st = p.stat()
                files[p.relative_to(ws).as_posix()] = (st.st_size, st.st_mtime_ns)
        for db in list(ws.rglob("*.sqlite"))[:12]:
            try:
                con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
                for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                           "'sqlite_%'"):
                    tables[f"{db.relative_to(ws).as_posix()}::{name}"] = con.execute(
                        f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                con.close()
            except sqlite3.Error:
                pass
    return {"files": files, "tables": tables, "contents": rowdiff.contents(ws)}


def diff(before: dict, after: dict) -> dict:
    added = sorted(set(after["files"]) - set(before["files"]))
    changed = sorted(k for k in set(after["files"]) & set(before["files"]) if after["files"][k] != before["files"][k])
    removed = sorted(set(before["files"]) - set(after["files"]))
    tables = [{"table": k, "before": before["tables"].get(k, 0), "after": v}
              for k, v in sorted(after["tables"].items()) if before["tables"].get(k) != v]
    return {"added": added, "changed": changed, "removed": removed, "tables": tables,
            "rows": rowdiff.changes(before.get("contents", {}), after.get("contents", {}))}


def mask(line: str, workspace: Path) -> str:
    """Show paths relative to the run or the repository, never this machine's folder names."""
    for path, label in ((workspace, "<workspace>"), (ROOT, "<repo>"), (Path(sys.base_prefix), "<python>"),
                        (Path.home(), "~")):
        for form in {str(path), str(path.resolve()), path.as_posix(), path.resolve().as_posix()}:
            line = line.replace(form, label)
    return line


def start_run(key: str, experiment: dict | None = None, auto: bool = False) -> Run:
    """Start a demo. An experiment either edits the inputs after a scene, or switches one safeguard off."""
    if key not in PROJECTS:
        raise ValueError(f"unknown pipeline {key}")
    run_id = f"{key}-{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
    ws = RUNS / run_id
    ws.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CIVICWORKS_STEP": "1", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    env.pop("CIVICWORKS_SAFEGUARD_OFF", None)
    if experiment and experiment.get("safeguard"):
        env["CIVICWORKS_SAFEGUARD_OFF"] = experiment["safeguard"]
    proc = subprocess.Popen([sys.executable, "-m", key, "demo", "--out", str(ws)], cwd=ROOT / PROJECTS[key],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", env=env, creationflags=NO_WINDOW, bufsize=1)
    run = Run(run_id, key, ws, proc, experiment=experiment, auto=auto)
    run.snapshots.append(snapshot(ws))
    with RUN_LOCK:
        ACTIVE[run_id] = run
    threading.Thread(target=_reader, args=(run,), daemon=True).start()
    return run


def _reader(run: Run) -> None:
    for raw in run.proc.stdout:
        line = raw.rstrip("\n")
        if line.startswith("@@ waiting"):
            _pause(run)
            continue
        if line.startswith("== "):
            try:
                run.scene = int(line[3:].split(".", 1)[0])
            except ValueError:
                pass
        with RUN_LOCK:
            run.lines.append({"scene": run.scene, "text": mask(line, run.workspace)})
    run.exit_code = run.proc.wait()
    _pause(run, final=True)


def _pause(run: Run, final: bool = False) -> None:
    snap = snapshot(run.workspace)
    change = diff(run.snapshots[-1], snap)
    with RUN_LOCK:
        said = "\n".join(line["text"] for line in run.lines if line["scene"] == run.scene)
    change["traced"] = rowdiff.trace(snap["contents"], said)
    run.changes[run.scene] = change
    run.snapshots.append(snap)
    exp = run.experiment
    if exp and exp.get("safeguard") and run.applied is None:
        run.applied = {"edits": [], "safeguard": exp["safeguard"], "rows": []}
    if exp and exp.get("edits") and not final and run.applied is None and run.scene == exp.get("after", 1):
        _apply_experiment(run, exp)
    run.status = "done" if final else "paused"
    if run.auto and not final:
        next_scene(run)


def _apply_experiment(run: Run, exp: dict) -> None:
    before = rowdiff.contents(run.workspace)
    try:
        done = experiments.apply(run.workspace, exp["edits"])
        after = rowdiff.contents(run.workspace)
        run.applied = {"edits": done, "rows": rowdiff.changes(before, after)}
    except (experiments.ExperimentError, OSError, sqlite3.Error) as exc:
        run.applied = {"error": str(exc), "edits": []}
    run.snapshots[-1] = snapshot(run.workspace)       # the next scene shows only what the pipeline did
    with RUN_LOCK:
        for text in run.applied["edits"] or [run.applied.get("error", "")]:
            run.lines.append({"scene": run.scene, "text": f"~~ experiment: {text}"})


BASELINES: dict[str, Run] = {}


def find_experiment(key: str, exp_id: str) -> dict:
    spec = CONTENT["experiments"].get(key, {})
    exp = next((e for e in spec.get("experiments", []) + spec.get("safeguards", []) if e["id"] == exp_id), None)
    if exp is None:
        raise ValueError(f"unknown experiment {exp_id}")
    return exp


def start_experiment(key: str, exp_id: str) -> dict:
    exp = find_experiment(key, exp_id)
    base = BASELINES.get(key)
    if base is None or (base.status == "done" and base.exit_code != 0):
        base = BASELINES[key] = start_run(key, auto=True)
    test = start_run(key, experiment=exp, auto=True)
    return {"normal": base.id, "experiment": test.id}


def compare_runs(a: Run, b: Run) -> list[dict]:
    with RUN_LOCK:
        return experiments.compare(list(a.lines), [x for x in b.lines if not x["text"].startswith("~~ ")
                                                   and "TEACHING SWITCH" not in x["text"]])


# --- the run's data: SQL console and editable CSV inputs -------------------------------------------------
def run_dbs(run: Run) -> list[str]:
    return sorted(p.relative_to(run.workspace).as_posix() for p in run.workspace.rglob("*.sqlite")) \
        if run.workspace.exists() else []


def run_sql(path: Path, sql: str, limit: int = 200) -> dict:
    """Run one statement against a run database. It is a sandbox: writes are allowed, but only here."""
    if path.suffix != ".sqlite":
        raise ValueError("SQL runs only against the run's .sqlite files")
    con = sqlite3.connect(path)
    try:
        cur = con.execute(sql)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = [["" if v is None else str(v) for v in r] for r in cur.fetchmany(limit + 1)]
            return {"cols": cols, "rows": rows[:limit], "more": len(rows) > limit}
        con.commit()
        return {"cols": [], "rows": [], "changed": cur.rowcount}
    finally:
        con.close()


def save_csv(path: Path, rows: list[list[str]]) -> int:
    import csv

    if path.suffix != ".csv" or len(rows) < 1 or len({len(r) for r in rows}) != 1:
        raise ValueError("a CSV needs a header row and the same number of cells in every row")
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return len(rows) - 1


def next_scene(run: Run) -> None:
    if run.status == "paused" and run.proc.poll() is None:
        run.status = "running"
        run.proc.stdin.write("\n")
        run.proc.stdin.flush()


def confined(run: Run, rel: str) -> Path:
    path = (run.workspace / rel).resolve()
    if run.workspace.resolve() not in path.parents:
        raise PermissionError("outside the run's workspace")
    return path


# --- previews -----------------------------------------------------------------------------------------
def preview(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        import csv

        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        return {"kind": "table", "sheets": [{"name": path.name, "rows": rows[:PREVIEW_ROWS + 1],
                                             "total": max(0, len(rows) - 1)}]}
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(path)
        sheets = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, PREVIEW_ROWS), max_col=min(ws.max_column, 14)):
                rows.append([("ƒ " + c.value) if isinstance(c.value, str) and c.value.startswith("=")
                             else ("" if c.value is None else str(c.value)) for c in row])
            sheets.append({"name": ws.title, "rows": rows, "total": ws.max_row, "charts": len(ws._charts)})
        return {"kind": "table", "sheets": sheets, "note": "Cells starting with ƒ are live Excel formulas."}
    if suffix == ".docx":
        from docx import Document

        doc = Document(path)
        parts = []
        for block in doc.element.body.iterchildren():
            tag = block.tag.rsplit("}", 1)[-1]
            if tag == "p":
                from docx.text.paragraph import Paragraph

                p = Paragraph(block, doc)
                if p.text.strip():
                    name = p.style.name
                    level = name.replace("Heading ", "h") if name.startswith(("Heading", "Title")) else ""
                    parts.append({"type": "p", "style": level or ("title" if p.style.name == "Title" else ""),
                                  "text": p.text})
            elif tag == "tbl":
                from docx.table import Table

                t = Table(block, doc)
                parts.append({"type": "table", "rows": [[c.text for c in r.cells] for r in t.rows][:40]})
        return {"kind": "doc", "parts": parts}
    if suffix == ".pdf":
        import pymupdf

        doc = pymupdf.open(path)
        info = {"kind": "pdf", "pages": doc.page_count, "toc": doc.get_toc()}
        doc.close()
        return info
    if suffix in (".sqlite", ".db"):
        return {"kind": "sqlite", **describe_db(path)}
    if suffix in (".png", ".jpg"):
        return {"kind": "image"}
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".json":
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    return {"kind": "text", "text": text[:60000], "html": suffix == ".html"}


def describe_db(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    tables = []
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                               "ORDER BY name"):
        cols = [{"name": c[1], "type": c[2], "notnull": bool(c[3]), "pk": bool(c[5])}
                for c in con.execute(f'PRAGMA table_info("{name}")')]
        fks = [{"from": f[3], "table": f[2], "to": f[4]} for f in con.execute(f'PRAGMA foreign_key_list("{name}")')]
        count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        tables.append({"name": name, "columns": cols, "foreign_keys": fks, "rows": count})
    con.close()
    return {"tables": tables}


def table_rows(path: Path, table: str) -> dict:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in names:
        raise ValueError("no such table")
    cur = con.execute(f'SELECT * FROM "{table}" LIMIT {PREVIEW_ROWS}')
    rows = [[d[0] for d in cur.description]] + [["" if v is None else str(v) for v in r] for r in cur.fetchall()]
    con.close()
    return {"kind": "table", "sheets": [{"name": table, "rows": rows}]}


def pdf_page(path: Path, page: int) -> bytes:
    import pymupdf

    doc = pymupdf.open(path)
    png = doc[max(0, min(page, doc.page_count - 1))].get_pixmap(dpi=110).tobytes("png")
    doc.close()
    return png


# --- quick run ----------------------------------------------------------------------------------------
QUICK: dict = {"status": "idle", "results": []}


def quick_run() -> None:
    QUICK.update(status="running", results=[])
    for key, folder in PROJECTS.items():
        out = RUNS / f"quick-{key}"
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
        start = time.time()
        proc = subprocess.run([sys.executable, "-m", key, "demo", "--out", str(out)], cwd=ROOT / folder,
                              capture_output=True, text=True, encoding="utf-8", creationflags=NO_WINDOW,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        files = sum(1 for p in out.rglob("*") if p.is_file()) if out.exists() else 0
        QUICK["results"].append({"key": key, "ok": proc.returncode == 0, "seconds": round(time.time() - start, 1),
                                 "files": files, "folder": str(out), "tail": proc.stdout.splitlines()[-3:]})
    QUICK["status"] = "done"


# --- HTTP -----------------------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _send(self, body: bytes, ctype: str = "application/json", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"), code=code)

    def _run(self, q) -> Run:
        run = ACTIVE.get(q.get("run", [""])[0])
        if run is None:
            raise KeyError("no such run")
        return run

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                return self._send((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path.startswith("/static/"):
                path = (STATIC / url.path[len("/static/"):]).resolve()
                if STATIC.resolve() not in path.parents:
                    raise PermissionError
                return self._send(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            if url.path.startswith("/videos/"):
                path = (ROOT / "docs" / "videos" / Path(url.path).name)
                return self._send(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "video/mp4")
            if url.path == "/api/ping":
                return self._json({"ok": True})
            if url.path == "/api/content":
                return self._json(CONTENT)
            if url.path == "/api/state":
                run = self._run(q)
                since = int(q.get("since", ["0"])[0])
                with RUN_LOCK:
                    lines = run.lines[since:]
                return self._json({"id": run.id, "key": run.key, "status": run.status, "scene": run.scene,
                                   "exit": run.exit_code, "lines": lines, "next": since + len(lines),
                                   "changes": run.changes, "applied": run.applied})
            if url.path == "/api/notes":
                return self._json(read_notes())
            if url.path == "/api/compare":
                return self._json({"lines": compare_runs(ACTIVE[q["a"][0]], ACTIVE[q["b"][0]])})
            if url.path == "/api/csv":
                import csv

                path = confined(self._run(q), q["path"][0])
                if path.suffix != ".csv":
                    raise ValueError("not a CSV file")
                with path.open(encoding="utf-8", newline="") as f:
                    rows = list(csv.reader(f))
                if len(rows) > 3000:
                    raise ValueError("too large to edit here; open it in a spreadsheet")
                return self._json({"rows": rows})
            if url.path == "/api/dbs":
                return self._json({"dbs": run_dbs(self._run(q))})
            if url.path == "/api/latest":
                key = q["key"][0]
                runs = [r for r in ACTIVE.values() if r.key == key and r.experiment is None and r.workspace.exists()]
                runs.sort(key=lambda r: r.started)
                return self._json({"run": runs[-1].id if runs else None, "status": runs[-1].status if runs else None})
            if url.path == "/api/files":
                run = self._run(q)
                files = sorted(p.relative_to(run.workspace).as_posix() for p in run.workspace.rglob("*")
                               if p.is_file()) if run.workspace.exists() else []
                return self._json({"files": files})
            if url.path == "/api/preview":
                return self._json(preview(confined(self._run(q), q["path"][0])))
            if url.path == "/api/rows":
                return self._json(table_rows(confined(self._run(q), q["path"][0]), q["table"][0]))
            if url.path == "/api/pdfpage":
                path = confined(self._run(q), q["path"][0])
                return self._send(pdf_page(path, int(q.get("page", ["0"])[0])), "image/png")
            if url.path == "/api/raw":
                path = confined(self._run(q), q["path"][0])
                ctype = mimetypes.guess_type(path.name)[0] or "text/plain"
                return self._send(path.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
            if url.path == "/api/quick":
                return self._json(QUICK)
            return self._json({"error": "not found"}, 404)
        except (KeyError, ValueError, PermissionError, FileNotFoundError) as exc:
            return self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 400)

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            if url.path == "/api/start":
                run = start_run(body["key"])
                return self._json({"run": run.id})
            if url.path == "/api/notes":
                save_note(str(body["key"])[:80], str(body["text"]))
                return self._json({"ok": True})
            if url.path == "/api/experiment":
                return self._json(start_experiment(body["key"], body["id"]))
            if url.path == "/api/sql":
                return self._json(run_sql(confined(ACTIVE[body["run"]], body["db"]), body["sql"]))
            if url.path == "/api/save-csv":
                run = ACTIVE[body["run"]]
                if run.status == "running":
                    raise ValueError("wait until the run is paused")
                return self._json({"rows": save_csv(confined(run, body["path"]), body["rows"])})
            if url.path == "/api/run-through":
                return self._json({"run": start_run(body["key"], auto=True).id})
            if url.path == "/api/next":
                next_scene(ACTIVE[body["run"]])
                return self._json({"ok": True})
            if url.path == "/api/quick":
                if QUICK["status"] != "running":
                    threading.Thread(target=quick_run, daemon=True).start()
                    time.sleep(0.2)
                return self._json(QUICK)
            if url.path == "/api/open-folder":
                folder = confined(ACTIVE[body["run"]], ".") if body.get("run") else Path(body["folder"])
                if RUNS.resolve() in folder.resolve().parents or folder.resolve() == RUNS.resolve():
                    _reveal(folder)
                return self._json({"ok": True})
            if url.path == "/api/quit":
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return None
            return self._json({"error": "not found"}, 404)
        except (KeyError, ValueError, PermissionError, sqlite3.Error) as exc:
            return self._json({"error": f"{exc.__class__.__name__}: {exc}"}, 400)


def _reveal(folder: Path) -> None:
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 - local Lab only, confined to its run folders
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


def serve(port: int = 8870, open_browser: bool = True) -> None:
    import socket
    import urllib.request
    import webbrowser

    url = f"http://127.0.0.1:{port}/"
    try:
        urllib.request.urlopen(url + "api/ping", timeout=1)
        if open_browser:
            webbrowser.open(url)          # already running: just show it
        return
    except OSError:
        pass
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"CivicWorks Lab on {url} (Ctrl+C or the Quit button to stop)", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        for run in ACTIVE.values():
            if run.proc.poll() is None:
                run.proc.kill()

