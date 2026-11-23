"""Record a narrated walkthrough video of each CivicWorks project from a real run.

For each project:
  1. run its test suite and its demo command, capturing every printed line (nothing is typed by hand)
  2. render the real outputs it produced: Excel sheets and Word pages through the installed Office apps
     (invisible, read-only), the status page through headless Edge, text files as document panels
  3. compose 1280x720 frames - the terminal replay at reading speed, then the outputs - with a caption
     explaining each scene, and encode an MP4 with ffmpeg
  4. write WebVTT captions and a Markdown transcript beside the video

Usage: python tools/make_videos.py [project ...]   (default: all six)
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
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_scripts import SCRIPTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "videos"
WORK = ROOT / "build" / "video-runs"
FFMPEG = shutil.which("ffmpeg") or r"C:\Program Files\ShareX\ffmpeg.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
W, H, FPS = 1280, 720, 15
FONTS = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"

# light palette (deliberately not a dark terminal)
BG, PANEL, BORDER, INK, MUTED = "#EEF2F5", "#FFFFFF", "#D3DBE3", "#1D2733", "#5A6878"
ACCENT, GOOD, BAD, WARN = "#1F6F8B", "#1E7A46", "#A8322D", "#8A5A00"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_TITLE, F_H, F_BODY, F_SMALL = font("seguisb.ttf", 40), font("seguisb.ttf", 22), font("segoeui.ttf", 19), \
    font("segoeui.ttf", 15)
F_MONO, F_MONO_B = font("CascadiaMono.ttf", 15), font("consolab.ttf", 15)
LINE_H, COLS = 21, 124


# --------------------------------------------------------------------------------------------- capture
@dataclass
class Capture:
    command: str
    lines: list[str]
    seconds: float
    exit_code: int
    tests: str


def run_capture(key: str) -> Capture:
    spec = SCRIPTS[key]
    project = ROOT / spec["dir"]
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    tests = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=project, capture_output=True,
                           text=True, env=env, creationflags=NO_WINDOW, timeout=900)
    summary = re.search(r"(\d+) passed[^\n]*", tests.stdout)
    out_dir = WORK / key
    if out_dir.exists():
        for p in out_dir.rglob("*"):
            if p.is_file():
                p.chmod(0o666)
        shutil.rmtree(out_dir)
    argv = [py, "-m", key, "demo", "--out", str(out_dir)]
    start = time.monotonic()
    proc = subprocess.run(argv, cwd=project, capture_output=True, text=True, env=env, encoding="utf-8",
                          creationflags=NO_WINDOW, timeout=900)
    seconds = time.monotonic() - start
    lines = [ln.replace(str(out_dir), "build/demo").replace(str(out_dir).replace("\\", "/"), "build/demo")
             for ln in proc.stdout.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    return Capture(f"python -m {key} demo --out build/demo", lines, seconds, proc.returncode,
                   summary.group(0).split(" in ")[0] if summary else "tests did not run")


# --------------------------------------------------------------------------------------------- outputs
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
                except Exception:  # noqa: BLE001
                    pass


def pdf_page_png(pdf: Path, page: int, png: Path) -> Path:
    doc = pymupdf.open(pdf)
    pix = doc[min(page, len(doc) - 1)].get_pixmap(dpi=150)
    pix.save(png)
    doc.close()
    img = Image.open(png).convert("RGB")
    bbox = Image.eval(img.convert("L"), lambda v: 255 - v).point(lambda v: 255 if v > 12 else 0).getbbox()
    if bbox:
        pad = 24
        img = img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(img.width, bbox[2] + pad),
                        min(img.height, bbox[3] + pad)))
    img.save(png)
    return png


def html_png(html: Path, png: Path) -> Path:
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1280,1100",
                    f"--screenshot={png}", html.resolve().as_uri()], capture_output=True, timeout=120,
                   creationflags=NO_WINDOW)
    return png


def text_png(text: str, title: str, png: Path) -> Path:
    lines = []
    for raw in text.splitlines()[:40]:
        lines += textwrap.wrap(raw, 96) or [""]
    lines = lines[:30]
    img = Image.new("RGB", (1100, 70 + LINE_H * len(lines) + 30), PANEL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 44], fill="#F3F6F9")
    d.text((20, 11), title, font=F_H, fill=INK)
    for i, ln in enumerate(lines):
        d.text((20, 60 + i * LINE_H), ln, font=F_MONO, fill=INK)
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
        path = matches[0]
        png = tmp / f"{key}-{n}.png"
        if kind == "excel":
            pdf = tmp / f"{key}-{n}.pdf"
            office.excel_sheet(path, extra, pdf)
            pdf_page_png(pdf, 0, png)
            label = f"{path.name} - {extra} tab"
        elif kind == "word":
            pdf = tmp / f"{key}-{n}.pdf"
            office.word_doc(path, pdf)
            pdf_page_png(pdf, int(extra or 1) - 1, png)
            label = f"{path.name} - page {extra or 1}"
        elif kind == "html":
            html_png(path, png)
            label = path.name
        else:
            text = path.read_text(encoding="utf-8")
            if kind == "json_head":
                data = json.loads(text)
                for s in data.get("stages", []):
                    s.pop("detail", None)
                text = json.dumps({k: data[k] for k in ("project_id", "run_id", "verdict", "fixture_seed",
                                                         "code_version", "environment", "stages", "outputs")},
                                  indent=2)
            text_png(text, path.name, png)
            label = path.relative_to(base).as_posix()
        shots.append((png, caption, label))
    return shots


# --------------------------------------------------------------------------------------------- frames
def colour_for(line: str) -> tuple[str, ImageFont.FreeTypeFont]:
    s = line.strip()
    if s.startswith("=="):
        return ACCENT, F_MONO_B
    if re.search(r"\b(BLOCKED|REFUSED|VERIFY-FAILED|FAILED|failed|rejected|overdue)\b|\[x\]|!!", s):
        return BAD, F_MONO
    if re.search(r"\b(PUBLISHED|APPROVED|COMPLETE|FINAL|accepted|OK)\b", s):
        return GOOD, F_MONO
    if s.startswith("[-]") or "awaiting-approval" in s or "held" in s or "NOTHING NEW" in s:
        return WARN, F_MONO
    return INK, F_MONO


def chrome(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 52], fill=PANEL)
    d.line([0, 52, W, 52], fill=BORDER)
    d.text((32, 13), title, font=F_H, fill=INK)
    tag = "CivicWorks Automation Lab  |  synthetic data"
    d.text((W - 32 - d.textlength(tag, font=F_SMALL), 18), tag, font=F_SMALL, fill=MUTED)
    return img, d


def caption(d: ImageDraw.ImageDraw, heading: str, body: str) -> None:
    top = H - 104
    d.rectangle([0, top, W, H], fill=PANEL)
    d.line([0, top, W, top], fill=BORDER)
    d.rectangle([0, top, 6, H], fill=ACCENT)
    d.text((32, top + 12), heading, font=F_H, fill=INK)
    for i, ln in enumerate(textwrap.wrap(body, 118)[:2]):
        d.text((32, top + 44 + i * 25), ln, font=F_BODY, fill=MUTED)


def terminal_frame(title: str, command: str, typed: str, buffer: list[str], heading: str, body: str) -> Image.Image:
    img, d = chrome(title)
    x0, y0, x1, y1 = 32, 68, W - 32, H - 120
    d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=PANEL, outline=BORDER)
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y0 + 30], fill="#F3F6F9")
    for i, c in enumerate(("#E06C5B", "#E5B648", "#5DB36B")):
        d.ellipse([x0 + 14 + i * 20, y0 + 10, x0 + 26 + i * 20, y0 + 22], fill=c)
    d.text((x0 + 84, y0 + 7), f"PowerShell  -  {command}", font=F_SMALL, fill=MUTED)
    visible = (y1 - y0 - 44) // LINE_H
    rows = [("PS> " + typed, ACCENT, F_MONO_B)] + [(ln, *colour_for(ln)) for ln in buffer]
    for i, (text, colour, f) in enumerate(rows[-visible:]):
        d.text((x0 + 16, y0 + 40 + i * LINE_H), text, font=f, fill=colour)
    caption(d, heading, body)
    return img


def readable(art: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Trim the page background, then, for a tall page, keep its top so the text is large enough to read."""
    bg = art.getpixel((2, 2))
    diff = Image.eval(Image.merge("RGB", [ch.point(lambda v, b=b: 255 if abs(v - b) > 10 else 0)
                                          for ch, b in zip(art.split(), bg, strict=True)]).convert("L"),
                      lambda v: 255 if v else 0)
    bbox = diff.getbbox()
    if bbox:
        art = art.crop((max(0, bbox[0] - 16), max(0, bbox[1] - 16), min(art.width, bbox[2] + 16),
                        min(art.height, bbox[3] + 16)))
    target = box_w / box_h * 0.62
    if art.width / art.height < target:
        art = art.crop((0, 0, art.width, int(art.width / target)))
    return art


def image_frame(title: str, shot: Path, label: str, heading: str, body: str) -> Image.Image:
    img, d = chrome(title)
    box_w, box_h = W - 64, H - 120 - 68 - 28
    art = readable(Image.open(shot).convert("RGB"), box_w, box_h)
    scale = min(box_w / art.width, box_h / art.height, 1.6)
    art = art.resize((max(1, int(art.width * scale)), max(1, int(art.height * scale))), Image.LANCZOS)
    x, y = (W - art.width) // 2, 68 + 26 + (box_h - art.height) // 2
    d.rectangle([x - 2, y - 2, x + art.width + 1, y + art.height + 1], outline=BORDER)
    img.paste(art, (x, y))
    d.text((32, 72), label, font=F_SMALL, fill=MUTED)
    caption(d, heading, body)
    return img


def card(title: str, big: str, lines: list[str], footer: str) -> Image.Image:
    img, d = chrome(title)
    d.text((80, 150), big, font=F_TITLE, fill=INK)
    y = 230
    for ln in lines:
        for part in textwrap.wrap(ln, 90):
            d.text((80, y), part, font=F_BODY, fill=INK)
            y += 30
        y += 8
    d.text((80, H - 90), footer, font=F_SMALL, fill=MUTED)
    return img


# --------------------------------------------------------------------------------------------- video
@dataclass
class Timeline:
    frames: list[tuple[Image.Image, int]] = field(default_factory=list)   # (frame, how many times)
    cues: list[tuple[float, float, str]] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return sum(n for _, n in self.frames) / FPS

    def add(self, frame: Image.Image, seconds: float) -> None:
        self.frames.append((frame, max(1, round(seconds * FPS))))

    def cue(self, start: float, text: str) -> None:
        self.cues.append((start, self.seconds, text))


def scenes(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    out = []
    for ln in lines:
        m = re.match(r"^== (\d+)\. (.+)$", ln.strip())
        if m:
            out.append((int(m.group(1)), m.group(2), [ln]))
        elif out:
            out[-1][2].append(ln)
    return out


def wrap_line(ln: str) -> list[str]:
    if len(ln) <= COLS:
        return [ln]
    indent = len(ln) - len(ln.lstrip())
    return textwrap.wrap(ln, COLS, subsequent_indent=" " * (indent + 4)) or [ln]


def build(key: str, cap: Capture, shots: list[tuple[Path, str, str]]) -> Timeline:
    spec = SCRIPTS[key]
    t = Timeline()
    title = spec["title"]
    start = t.seconds
    t.add(card(title, title, [spec["problem"], "", f"Command:  {cap.command}",
                              f"Real run: {cap.seconds:.1f} s.  Test suite: {cap.tests}.",
                              "The terminal below is replayed from that run at reading speed; nothing is typed by "
                              "hand."], "Every organisation, person and number in this video is invented."), 7)
    t.cue(start, f"{title}. {spec['problem']}")
    buffer: list[str] = []
    for typed in range(0, len(cap.command) + 1, 3):  # the command appears a few characters at a time
        frame = terminal_frame(title, cap.command, cap.command[:typed], buffer, "Running the demo",
                               "One command runs the whole story on a fresh, generated workspace.")
        t.add(frame, 1 / FPS)
    for number, heading, block in scenes(cap.lines):
        body = spec["scenes"].get(number, "")
        start = t.seconds
        for ln in block:
            for part in wrap_line(ln):
                buffer.append(part)
                t.add(terminal_frame(title, cap.command, cap.command, buffer, f"{number}. {heading}", body), 0.12)
        chars = sum(len(x) for x in block) + len(body)
        t.add(terminal_frame(title, cap.command, cap.command, buffer, f"{number}. {heading}", body),
              min(10.0, max(4.0, 2.0 + chars / 55)))
        t.cue(start, f"{number}. {heading}. {body}")
    for shot, text, label in shots:
        start = t.seconds
        t.add(image_frame(title, shot, label, "What it produced", text), 6.5)
        t.cue(start, f"What it produced: {label}. {text}")
    start = t.seconds
    t.add(card(title, "What this run showed", [f"•  {c}" for c in spec["close"]] +
               ["", f"Tests: {cap.tests}.  Demo exit code: {cap.exit_code}."],
               "Synthetic data only. Built with AI coding assistance to the author's design; every claim is "
               "covered by a test."), 7)
    t.cue(start, "What this run showed: " + "; ".join(spec["close"]) + f". Tests: {cap.tests}.")
    return t


def encode(t: Timeline, mp4: Path) -> None:
    mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                             f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf",
                             "26", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                             str(mp4)], stdin=subprocess.PIPE, creationflags=NO_WINDOW)
    for frame, count in t.frames:
        data = frame.tobytes()
        for _ in range(count):
            proc.stdin.write(data)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {mp4.name}")


def stamp(seconds: float) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_captions(key: str, t: Timeline, cap: Capture) -> None:
    vtt = ["WEBVTT", ""]
    md = [f"# {SCRIPTS[key]['title']} - transcript", "",
          f"Video length {t.seconds:.0f} s. Real demo run {cap.seconds:.1f} s; {cap.tests}.", ""]
    for start, end, text in t.cues:
        vtt += [f"{stamp(start)} --> {stamp(end)}", text, ""]
        md.append(f"- **{stamp(start)[3:8]}** {text}")
    md += ["", "## Terminal output (captured, unedited)", "", "```", *cap.lines, "```", ""]
    (OUT / f"{key}.vtt").write_text("\n".join(vtt), encoding="utf-8")
    (OUT / f"{key}.md").write_text("\n".join(md), encoding="utf-8")


def main(keys: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    office = Office()
    stats_file = OUT / "videos.json"
    report = json.loads(stats_file.read_text(encoding="utf-8")) if stats_file.exists() else {}
    try:
        for key in keys or list(SCRIPTS):
            print(f"== {key}")
            cap = run_capture(key)
            print(f"  demo exit {cap.exit_code} in {cap.seconds:.1f}s; {cap.tests}; {len(cap.lines)} lines")
            if cap.exit_code != 0:
                raise RuntimeError(f"{key} demo failed; not recording a video of a failure")
            shots = render_outputs(key, office, tmp)
            t = build(key, cap, shots)
            encode(t, OUT / f"{key}.mp4")
            write_captions(key, t, cap)
            subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-ss", "40", "-i", str(OUT / f"{key}.mp4"),
                            "-frames:v", "1", "-q:v", "4", str(OUT / f"{key}-poster.jpg")], check=True,
                           creationflags=NO_WINDOW)
            report[key] = {"seconds": round(t.seconds), "real_run": round(cap.seconds, 1), "tests": cap.tests,
                           "mb": round((OUT / f"{key}.mp4").stat().st_size / 1e6, 1)}
            print(f"  video {report[key]['seconds']} s, {report[key]['mb']} MB")
    finally:
        office.quit()
    stats_file.write_text(json.dumps({k: report[k] for k in SCRIPTS if k in report}, indent=2) + "\n",
                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
