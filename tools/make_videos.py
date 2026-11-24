"""Narrated walkthrough videos of each CivicWorks pipeline, made from real runs, plus an overview reel.

For each pipeline:
  1. run its tests and its demo, capturing every printed line (the terminal text is never typed by hand)
  2. render the real outputs: Excel sheets and Word pages through the installed Office apps (invisible,
     read-only), PDF pages directly, HTML pages through headless Edge, text files as document panels
  3. narrate each segment with a built-in Windows voice, from learn/pipelines/<key>.yaml - the same words
     the Lab and the documentation site use
  4. compose 1600x900 frames - title, then each scene (terminal on the left, plain explanation and result
     on the right, progress along the bottom), then the outputs, then a summary - with crossfades
  5. encode MP4 (H.264 + AAC) with ffmpeg; write WebVTT captions, a transcript and a poster

Usage: python tools/make_videos.py [key ...] [--overview]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import yaml
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrate import speak  # noqa: E402
from video_scripts import SCRIPTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "videos"
IMG = ROOT / "docs" / "img"
WORK = ROOT / "build" / "video-runs"
FFMPEG = shutil.which("ffmpeg") or r"C:\Program Files\ShareX\ffmpeg.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
W, H, FPS = 1600, 900, 15
FADE = 0.45
FONTS = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
REPO_URL = "github.com/data-dl/civicworks-automation-lab"

BG, PANEL, LINE, INK, MUTED = "#F4F6F9", "#FFFFFF", "#DDE3EA", "#1B2430", "#5B6877"
ACCENT, ACCENT_SOFT, GOOD, GOOD_SOFT, BAD, WARN = "#2F5D8A", "#E6EEF7", "#2D6F57", "#E4F1EC", "#A8402F", "#8A6214"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_HERO, F_TITLE, F_H, F_BODY, F_SMALL = (font("seguisb.ttf", 54), font("seguisb.ttf", 30), font("seguisb.ttf", 24),
                                         font("segoeui.ttf", 22), font("segoeui.ttf", 17))
F_MONO, F_MONO_B, F_TAG = font("CascadiaMono.ttf", 16), font("consolab.ttf", 16), font("consolab.ttf", 15)
LINE_H = 23


def content(key: str) -> dict:
    return yaml.safe_load((ROOT / "learn" / "pipelines" / f"{key}.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------- capture
@dataclass
class Capture:
    command: str
    lines: list[str]
    seconds: float
    exit_code: int
    tests: str


def run_capture(key: str) -> Capture:
    c = content(key)
    project = ROOT / c["dir"]
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    env.pop("CIVICWORKS_STEP", None)
    tests = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=project, capture_output=True,
                           text=True, env=env, creationflags=NO_WINDOW, timeout=1200, check=False)
    summary = re.search(r"(\d+) passed", tests.stdout)
    out_dir = WORK / key
    if out_dir.exists():
        for p in out_dir.rglob("*"):
            if p.is_file():
                p.chmod(0o666)
        shutil.rmtree(out_dir)
    start = time.monotonic()
    proc = subprocess.run([py, "-m", key, "demo", "--out", str(out_dir)], cwd=project, capture_output=True,
                          text=True, env=env, encoding="utf-8", creationflags=NO_WINDOW, timeout=1200, check=False)
    seconds = time.monotonic() - start
    lines = [ln.replace(str(out_dir), "build/demo").replace(str(out_dir).replace("\\", "/"), "build/demo")
             for ln in proc.stdout.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    return Capture(f"python -m {key} demo", lines, seconds, proc.returncode,
                   f"{summary.group(1)} tests passing" if summary else "tests did not run")


# ------------------------------------------------------------------------------------------- outputs
class Office:
    """Excel and Word, invisible, opened read-only, closed without saving."""

    def __init__(self):
        self.excel = self.word = None

    def excel_sheet(self, path: Path, sheet: str, pdf: Path) -> None:
        import win32com.client

        if self.excel is None:
            self.excel = win32com.client.DispatchEx("Excel.Application")
            self.excel.Visible, self.excel.DisplayAlerts = False, False
        wb = self.excel.Workbooks.Open(str(path), ReadOnly=True)
        try:
            ws = wb.Worksheets(sheet)
            ps = ws.PageSetup
            ps.Orientation, ps.Zoom, ps.FitToPagesWide, ps.FitToPagesTall = 2, False, 1, 1
            ps.PrintGridlines = True
            ws.ExportAsFixedFormat(0, str(pdf))
        finally:
            wb.Close(False)

    def word_doc(self, path: Path, pdf: Path) -> None:
        import win32com.client

        if self.word is None:
            self.word = win32com.client.DispatchEx("Word.Application")
            self.word.Visible, self.word.DisplayAlerts = False, 0
        doc = self.word.Documents.Open(str(path), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.ExportAsFixedFormat(str(pdf), 17)
        finally:
            doc.Close(False)

    def quit(self) -> None:
        for app in (self.excel, self.word):
            if app is not None:
                try:
                    app.Quit()
                except Exception:  # noqa: BLE001 - closing is best effort
                    pass


def trim(img: Image.Image, pad: int = 24) -> Image.Image:
    bg = img.getpixel((2, 2))
    mask = Image.merge("RGB", [ch.point(lambda v, b=b: 255 if abs(v - b) > 10 else 0)
                               for ch, b in zip(img.split(), bg, strict=True)]).convert("L")
    box = mask.getbbox()
    if not box:
        return img
    return img.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(img.width, box[2] + pad),
                     min(img.height, box[3] + pad)))


def pdf_png(pdf: Path, page: int, png: Path) -> Path:
    doc = pymupdf.open(pdf)
    doc[min(page, doc.page_count - 1)].get_pixmap(dpi=150).save(png)
    doc.close()
    trim(Image.open(png).convert("RGB")).save(png)
    return png


def html_png(html: Path, png: Path) -> Path:
    # its own fresh profile each try, so an open Edge window or a lingering headless one cannot swallow the request
    for attempt in range(3):
        profile = WORK / f"_edge-profile-{png.stem}-{attempt}"
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1400,1200",
                        f"--user-data-dir={profile}", "--no-first-run", "--virtual-time-budget=4000",
                        f"--screenshot={png}", html.resolve().as_uri()],
                       capture_output=True, timeout=120, creationflags=NO_WINDOW, check=False)
        if png.exists():
            break
        time.sleep(2)
    if not png.exists():
        raise RuntimeError(f"Edge did not write a screenshot of {html.name}")
    trim(Image.open(png).convert("RGB")).save(png)
    return png


def text_png(text: str, title: str, png: Path) -> Path:
    rows = []
    for raw in text.splitlines()[:44]:
        rows += textwrap.wrap(raw, 92) or [""]
    rows = rows[:28]
    img = Image.new("RGB", (1180, 84 + LINE_H * len(rows) + 30), PANEL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 54], fill="#F3F6F9")
    d.text((24, 13), title, font=F_H, fill=INK)
    for i, ln in enumerate(rows):
        d.text((24, 72 + i * LINE_H), ln, font=F_MONO, fill=INK)
    img.save(png)
    return png


def render_outputs(key: str, office: Office, tmp: Path) -> list[tuple[Path, str, str]]:
    base = WORK / key
    shots = []
    for n, (kind, spec, caption) in enumerate(SCRIPTS[key]["artifacts"]):
        target, _, extra = spec.partition("|")
        matches = sorted(base.glob(target))
        if not matches:
            print(f"  ! missing output {target}")
            continue
        path, png = matches[0], tmp / f"{key}-{n}.png"
        label = path.relative_to(base).as_posix()
        if kind == "excel":
            office.excel_sheet(path, extra, tmp / f"{key}-{n}.pdf")
            pdf_png(tmp / f"{key}-{n}.pdf", 0, png)
            label = f"{path.name}  -  {extra} tab"
        elif kind == "word":
            office.word_doc(path, tmp / f"{key}-{n}.pdf")
            pdf_png(tmp / f"{key}-{n}.pdf", int(extra or 1) - 1, png)
            label = f"{path.name}  -  page {extra or 1}"
        elif kind == "pdf":
            pdf_png(path, int(extra or 1) - 1, png)
            label = f"{path.name}  -  page {extra or 1}"
        elif kind == "html":
            html_png(path, png)
        else:
            text = path.read_text(encoding="utf-8")
            if kind == "json_head":
                data = json.loads(text)
                for s in data.get("stages", []):
                    s.pop("detail", None)
                text = json.dumps({k: data[k] for k in ("project_id", "run_id", "verdict", "fixture_seed",
                                                         "code_version", "stages", "outputs") if k in data}, indent=2)
            text_png(text, path.name, png)
        shots.append((png, caption, label))
    return shots


# ------------------------------------------------------------------------------------------- drawing
def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words, rows, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=f) <= width:
            cur = trial
        else:
            rows.append(cur)
            cur = w
    return rows + ([cur] if cur else [])


def chrome(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill=PANEL)
    d.line([0, 64, W, 64], fill=LINE)
    d.rounded_rectangle([36, 16, 70, 48], radius=7, fill=ACCENT)
    d.text((53, 32), "CW", font=F_TAG, fill="#FFFFFF", anchor="mm")
    d.text((84, 17), title, font=F_H, fill=INK)
    tag = "CivicWorks Automation Lab  |  synthetic data"
    d.text((W - 40 - d.textlength(tag, font=F_SMALL), 22), tag, font=F_SMALL, fill=MUTED)
    return img, d


def progress(d: ImageDraw.ImageDraw, total: int, now: int) -> None:
    y, x0, x1 = H - 26, 40, W - 40
    d.line([x0, y, x1, y], fill=LINE, width=4)
    if total:
        d.line([x0, y, x0 + (x1 - x0) * now / total, y], fill=ACCENT, width=4)
        for i in range(total):
            cx = x0 + (x1 - x0) * (i + 0.5) / total
            d.ellipse([cx - 6, y - 6, cx + 6, y + 6], fill=ACCENT if i < now else PANEL, outline=ACCENT, width=2)


def colour(line: str) -> tuple[str, ImageFont.FreeTypeFont]:
    s = line.strip()
    if s.startswith("=="):
        return ACCENT, F_MONO_B
    if re.search(r"\b(BLOCKED|REFUSED|VERIFY-FAILED|FAILED|QUARANTINED|STOPPED|rejected|overdue)\b|\[x\]|!!", s):
        return BAD, F_MONO
    if re.search(r"\b(PUBLISHED|APPROVED|COMPLETE|FINAL|accepted|verified|OK)\b", s):
        return GOOD, F_MONO
    if s.startswith("[-]") or "awaiting-approval" in s or "held" in s or "NOTHING NEW" in s or "stale" in s:
        return WARN, F_MONO
    return INK, F_MONO


def wrap_terminal(lines: list[str], cols: int = 92) -> list[str]:
    out = []
    for ln in lines:
        if len(ln) <= cols:
            out.append(ln)
        else:
            ind = len(ln) - len(ln.lstrip())
            out += textwrap.wrap(ln, cols, subsequent_indent=" " * (ind + 4))
    return out


def scene_frame(title: str, number: int, total: int, heading: str, explain: str, answer: str | None,
                term: list[str]) -> Image.Image:
    img, d = chrome(title)
    d.text((40, 84), f"SCENE {number} OF {total}", font=F_TAG, fill=ACCENT)
    d.text((40, 108), heading, font=F_TITLE, fill=INK)
    # terminal (left)
    x0, y0, x1, y1 = 40, 162, 1000, H - 52
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill="#FBFCFE", outline=LINE)
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y0 + 34], fill="#F1F4F8")
    for i, c in enumerate(("#D9826F", "#E3BC5F", "#7DB48F")):
        d.ellipse([x0 + 16 + i * 20, y0 + 11, x0 + 28 + i * 20, y0 + 23], fill=c)
    d.text((x0 + 90, y0 + 8), "terminal  -  real output, replayed", font=F_SMALL, fill=MUTED)
    visible = (y1 - y0 - 50) // LINE_H
    for i, ln in enumerate(term[-visible:]):
        col, f = colour(ln)
        d.text((x0 + 18, y0 + 46 + i * LINE_H), ln, font=f, fill=col)
    # explanation (right)
    rx = 1030
    d.rounded_rectangle([rx, y0, W - 40, y1], radius=10, fill=PANEL, outline=LINE)
    d.text((rx + 24, y0 + 20), "WHAT'S HAPPENING", font=F_TAG, fill=ACCENT)
    y = y0 + 52
    for row in wrap(d, explain, F_BODY, W - 40 - rx - 48):
        d.text((rx + 24, y), row, font=F_BODY, fill=INK)
        y += 31
    if answer:
        y += 16
        rows = wrap(d, answer, F_BODY, W - 40 - rx - 72)
        d.rounded_rectangle([rx + 20, y, W - 60, y + 46 + 30 * len(rows)], radius=8, fill=GOOD_SOFT)
        d.text((rx + 40, y + 14), "RESULT", font=F_TAG, fill=GOOD)
        for i, row in enumerate(rows):
            d.text((rx + 40, y + 40 + i * 30), row, font=F_BODY, fill=INK)
    progress(d, total, number)
    return img


def output_frame(title: str, shot: Path, label: str, caption: str, n: int, total: int) -> Image.Image:
    img, d = chrome(title)
    d.text((40, 84), f"WHAT IT PRODUCED  {n} OF {total}", font=F_TAG, fill=ACCENT)
    rows = wrap(d, caption, F_H, W - 80)
    for i, row in enumerate(rows[:2]):
        d.text((40, 108 + i * 32), row, font=F_H, fill=INK)
    top = 108 + 32 * min(2, len(rows)) + 18
    box_w, box_h = W - 80, H - top - 70
    art = Image.open(shot).convert("RGB")
    if art.width / art.height < (box_w / box_h) * 0.62:      # tall page: keep the readable top
        art = art.crop((0, 0, art.width, int(art.width / ((box_w / box_h) * 0.62))))
    scale = min(box_w / art.width, box_h / art.height, 1.5)
    art = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)
    x = (W - art.width) // 2
    d.rectangle([x - 2, top - 2, x + art.width + 1, top + art.height + 1], outline=LINE, width=2)
    img.paste(art, (x, top))
    d.text((40, H - 54), label, font=F_SMALL, fill=MUTED)
    return img


def card(title: str, eyebrow: str, big: str, body: list[str], chips: list[str], footer: str) -> Image.Image:
    img, d = chrome(title)
    d.text((110, 170), eyebrow.upper(), font=F_TAG, fill=ACCENT)
    y = 200
    for row in wrap(d, big, F_HERO, W - 260):
        d.text((110, y), row, font=F_HERO, fill=INK)
        y += 66
    y += 18
    for para in body:
        for row in wrap(d, para, F_BODY, W - 260):
            d.text((110, y), row, font=F_BODY, fill=MUTED if para.startswith("Real run") else INK)
            y += 32
        y += 10
    x, y = 110, y + 14
    for chip in chips:
        w = d.textlength(chip, font=F_SMALL) + 26
        if x + w > W - 110:
            x, y = 110, y + 40
        d.rounded_rectangle([x, y, x + w, y + 32], radius=16, fill=ACCENT_SOFT)
        d.text((x + 13, y + 6), chip, font=F_SMALL, fill=ACCENT)
        x += w + 10
    d.text((110, H - 80), footer, font=F_SMALL, fill=MUTED)
    return img


def flow_card(title: str, c: dict, cap: Capture) -> Image.Image:
    img = card(title, "CivicWorks pipeline", c["title"], [c["tagline"], f"Real run: {cap.seconds:.1f} seconds.  "
               f"{cap.tests}.  Terminal output below is replayed from that run."], [], "Every organisation, person "
               "and number here is invented.")
    d = ImageDraw.Draw(img)
    steps = c["steps"]
    gap, y, x0 = 14, 470, 110
    w = (W - 220 - gap * (len(steps) - 1)) / len(steps)
    d.text((x0, y - 34), "HOW IT WORKS", font=F_TAG, fill=ACCENT)
    for i, s in enumerate(steps):
        x = x0 + i * (w + gap)
        d.rounded_rectangle([x, y, x + w, y + 230], radius=10, fill=PANEL, outline=LINE)
        d.text((x + 14, y + 12), f"{i + 1}", font=F_TAG, fill=ACCENT)
        d.text((x + 14, y + 34), s["name"], font=F_H if w > 170 else F_BODY, fill=INK)
        for j, row in enumerate(wrap(d, s["plain"], F_SMALL, int(w) - 28)[:6]):
            d.text((x + 14, y + 72 + j * 23), row, font=F_SMALL, fill=MUTED)
        if i < len(steps) - 1:
            d.text((x + w + 1, y + 40), ">", font=F_H, fill=MUTED)
    return img


# ------------------------------------------------------------------------------------------- timeline
@dataclass
class Timeline:
    frames: list[tuple[Image.Image, int]] = field(default_factory=list)
    audio: list[tuple[float, Path]] = field(default_factory=list)
    cues: list[tuple[float, float, str]] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return sum(n for _, n in self.frames) / FPS

    def add(self, frame: Image.Image, seconds: float, fade: bool = False) -> None:
        if fade and self.frames:
            prev = self.frames[-1][0]
            steps = max(1, int(FADE * FPS))
            for i in range(1, steps + 1):
                self.frames.append((Image.blend(prev, frame, i / (steps + 1)), 1))
        self.frames.append((frame, max(1, round(seconds * FPS))))

    def say(self, text: str, wav: Path) -> float:
        length = speak(text, wav)
        self.audio.append((self.seconds + 0.25, wav))
        self.cues.append((self.seconds + 0.25, self.seconds + 0.25 + length, text))
        return length


def narrated_scene(t: Timeline, title: str, number: int, total: int, heading: str, explain: str, answer: str,
                   block: list[str], history: list[str], wavs: Path, tag: str) -> None:
    text = f"Scene {number}. {explain} {answer}"
    length = t.say(text, wavs / f"{tag}.wav")
    wrapped = wrap_terminal(block)
    typing = min(0.12 * len(wrapped), length * 0.45)
    first = True
    for i in range(1, len(wrapped) + 1):
        t.add(scene_frame(title, number, total, heading, explain, None, history + wrapped[:i]),
              typing / max(1, len(wrapped)), fade=first)
        first = False
    remaining = max(2.5, length + 0.9 - typing)
    t.add(scene_frame(title, number, total, heading, explain, answer, history + wrapped), remaining)
    history.extend(wrapped)


def build(key: str, cap: Capture, shots: list[tuple[Path, str, str]], wavs: Path) -> Timeline:
    c = content(key)
    t = Timeline()
    title = c["title"]
    intro = f"{title}. {c['tagline']}"
    length = t.say(intro, wavs / "intro.wav")
    t.add(flow_card(title, c, cap), max(6.0, length + 1.0))
    blocks = []
    for ln in cap.lines:
        m = re.match(r"^== (\d+)\. (.+)$", ln.strip())
        if m:
            blocks.append((int(m.group(1)), m.group(2), [ln]))
        elif blocks:
            blocks[-1][2].append(ln)
    history: list[str] = [f"PS> {cap.command}"]
    for number, heading, block in blocks:
        sc = c["scenes"].get(number, {"explain": "", "answer": ""})
        narrated_scene(t, title, number, len(blocks), heading, sc["explain"], sc["answer"], block, history, wavs,
                       f"scene{number}")
    for n, (shot, caption, label) in enumerate(shots, start=1):
        length = t.say(caption, wavs / f"out{n}.wav")
        t.add(output_frame(title, shot, label, caption, n, len(shots)), max(5.5, length + 1.4), fade=True)
    close = SCRIPTS[key]["close"]
    length = t.say("What this run showed: " + ". ".join(close) + ".", wavs / "close.wav")
    t.add(card(title, "What this run showed", "Checked, recorded, recoverable.", [f"-  {x}" for x in close]
               + [f"{cap.tests}, rerun by GitHub on Linux and Windows after every change."], c["skills"][:6],
               f"Source and documentation: {REPO_URL}"), max(7.0, length + 1.5), fade=True)
    return t


def mix_audio(t: Timeline, out: Path) -> Path:
    rate = 16000
    total = int((t.seconds + 1) * rate)
    pcm = bytearray(total * 2)
    for start, wav in t.audio:
        with wave.open(str(wav)) as w:
            data = w.readframes(w.getnframes())
            if w.getframerate() != rate:
                raise ValueError("unexpected sample rate")
        offset = int(start * rate) * 2
        pcm[offset:offset + len(data)] = data[: max(0, len(pcm) - offset)]
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    return out


def encode(t: Timeline, mp4: Path, audio: Path) -> None:
    mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                             f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset",
                             "medium", "-crf", "24", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac",
                             "-b:a", "80k", "-shortest", "-movflags", "+faststart", str(mp4)],
                            stdin=subprocess.PIPE, creationflags=NO_WINDOW)
    for frame, count in t.frames:
        data = frame.tobytes()
        for _ in range(count):
            proc.stdin.write(data)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {mp4.name}")


def stamp(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"00:{int(m):02d}:{s:06.3f}"


def write_captions(key: str, t: Timeline, extra_md: str = "") -> None:
    vtt = ["WEBVTT", ""]
    md = [f"# {key} - transcript", "", f"Length {t.seconds:.0f} s.", ""]
    for start, end, text in t.cues:
        for i, part in enumerate(textwrap.wrap(text, 160)):
            # split long narration into caption-sized pieces spread across its duration
            pieces = textwrap.wrap(text, 160)
            a = start + (end - start) * i / len(pieces)
            b = start + (end - start) * (i + 1) / len(pieces)
            vtt += [f"{stamp(a)} --> {stamp(b)}", part, ""]
        md.append(f"- **{stamp(start)[3:8]}** {text}")
    (OUT / f"{key}.vtt").write_text("\n".join(vtt), encoding="utf-8")
    (OUT / f"{key}.md").write_text("\n".join(md) + extra_md, encoding="utf-8")


def poster(t: Timeline, key: str) -> None:
    frame = t.frames[min(len(t.frames) - 1, len(t.frames) // 3)][0]
    frame.convert("RGB").resize((960, 540), Image.LANCZOS).save(OUT / f"{key}-poster.jpg", quality=86)


# ------------------------------------------------------------------------------------------- overview reel
def overview(shots_by_key: dict[str, list], tests: int) -> dict:
    wavs = WORK / "_audio" / "overview"
    wavs.mkdir(parents=True, exist_ok=True)
    t = Timeline()
    keys = sorted(SCRIPTS, key=lambda k: content(k)["order"])
    title = "CivicWorks Automation Lab"
    length = t.say("CivicWorks Automation Lab. Eight data pipelines for invented organisations. Each one takes messy "
                   "data, catches the problems, stops where a person must decide, and leaves evidence of everything "
                   "it did.", wavs / "intro.wav")
    t.add(card(title, "Portfolio overview", "Reliable automation, from messy inputs to verified outputs.",
               ["Eight pipelines. Invented data with planted problems. Real checks, approvals, rollback and "
                f"orchestration. {tests} automated tests, rerun on Linux and Windows after every change."],
               ["Python", "SQL / SQLite", "data quality", "Excel", "Word", "PDF", "JSON", "orchestration",
                "approvals", "checkpoints"], f"Source: {REPO_URL}"), max(7.0, length + 1.0))
    for n, key in enumerate(keys, start=1):
        c = content(key)
        shot = shots_by_key.get(key, [])
        length = t.say(f"{c['title']}. {c['tagline']}", wavs / f"{key}.wav")
        if shot:
            img = output_frame(f"{n} of 8  |  {c['title']}", shot[0][0], shot[0][2], c["tagline"], n, 8)
        else:
            img = card(c["title"], f"pipeline {n} of 8", c["title"], [c["tagline"]], c["skills"][:5], "")
        t.add(img, max(5.5, length + 1.0), fade=True)
    length = t.say("Every pipeline can be run step by step in the CivicWorks Lab, with a plain-language explanation "
                   "of each scene, and every claim is backed by a test.", wavs / "close.wav")
    t.add(card(title, "See it run", "Run it, watch it, check it.",
               ["Each pipeline has its own narrated walkthrough.", "The CivicWorks Lab runs any pipeline one scene "
                "at a time and shows exactly which files and tables changed."], [], f"Source: {REPO_URL}"),
          max(6.0, length + 1.0), fade=True)
    audio = mix_audio(t, wavs / "mix.wav")
    encode(t, OUT / "overview.mp4", audio)
    write_captions("overview", t)
    poster(t, "overview")
    return {"seconds": round(t.seconds), "mb": round((OUT / "overview.mp4").stat().st_size / 1e6, 1)}


def main(args: list[str]) -> int:
    want_overview = "--overview" in args
    keys = [a for a in args if not a.startswith("--")] or sorted(SCRIPTS, key=lambda k: content(k)["order"])
    OUT.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    stats_file = OUT / "videos.json"
    stats = json.loads(stats_file.read_text(encoding="utf-8")) if stats_file.exists() else {}
    office = Office()
    shots_by_key = {}
    try:
        for key in keys:
            print(f"== {key}", flush=True)
            cap = run_capture(key)
            print(f"  demo exit {cap.exit_code} in {cap.seconds:.1f}s; {cap.tests}; {len(cap.lines)} lines", flush=True)
            if cap.exit_code != 0:
                raise RuntimeError(f"{key} demo failed; not recording a video of a failure")
            shots = render_outputs(key, office, tmp)
            shots_by_key[key] = shots
            for i, (png, _, _) in enumerate(shots):
                shutil.copyfile(png, IMG / f"{key}-{i + 1}.png")
            wavs = WORK / "_audio" / key
            wavs.mkdir(parents=True, exist_ok=True)
            t = build(key, cap, shots, wavs)
            encode(t, OUT / f"{key}.mp4", mix_audio(t, wavs / "mix.wav"))
            write_captions(key, t, "\n\n## Terminal output (captured, unedited)\n\n```\n" + "\n".join(cap.lines) + "\n```\n")
            poster(t, key)
            stats[key] = {"seconds": round(t.seconds), "real_run": round(cap.seconds, 1), "tests": cap.tests,
                          "mb": round((OUT / f"{key}.mp4").stat().st_size / 1e6, 1)}
            print(f"  video {stats[key]['seconds']} s, {stats[key]['mb']} MB", flush=True)
            stats_file.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")   # keep each one, even if a later video fails
        if want_overview:
            for key in SCRIPTS:
                if key not in shots_by_key:
                    shots_by_key[key] = [(IMG / f"{key}-1.png", "", content(key)["title"])] \
                        if (IMG / f"{key}-1.png").exists() else []
            total = sum(int(v["tests"].split()[0]) for v in stats.values() if v["tests"][0].isdigit())
            stats["overview"] = overview(shots_by_key, total)
            print(f"  overview {stats['overview']}", flush=True)
    finally:
        office.quit()
    stats_file.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
