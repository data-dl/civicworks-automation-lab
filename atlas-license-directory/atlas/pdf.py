"""Print the directory editions from the frozen snapshot, then check each PDF as a reader would.

Layout is planned before anything is drawn, so the contents page and the index know every page
number in advance - no fixed page assumptions. Each PDF gets a cover, a linked contents page, one
section per craft, an alphabetical index with links back to each listing, and bookmarks.

Verification opens the finished file and checks it independently of the code that drew it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pymupdf

from .synth import DISTRICTS

EDITIONS = {
    "public": {"label": "Public", "states": ("active",), "detail": False},
    "member": {"label": "Member", "states": ("active",), "detail": True},
    "inspector": {"label": "Inspector", "states": ("active", "suspended"), "detail": True},
}
W, H, M = 612, 792, 54
ENTRIES_PER_PAGE, INDEX_PER_PAGE = 13, 40
TITLE = "Four Districts Craft Coalition"


@dataclass
class Entry:
    member_id: str
    name: str
    studio: str
    venue: str
    craft: str
    endorsement: str
    valid_to: str
    state: str


@dataclass
class Plan:
    district: str
    edition: str
    sections: list[tuple[str, list[Entry]]]
    section_pages: dict[str, list[int]] = field(default_factory=dict)
    entry_page: dict[str, int] = field(default_factory=dict)
    index_pages: list[int] = field(default_factory=list)
    page_count: int = 0


def _key(e: Entry) -> str:
    return f"{e.member_id}|{e.craft}|{e.studio}"


def read_entries(snapshot: Path, district: str, edition: str) -> list[Entry]:
    con = sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True)
    states = EDITIONS[edition]["states"]
    rows = con.execute(
        "SELECT m.member_id, m.invented_name, s.studio_name, s.venue_token, c.label, e.endorsement_id, e.valid_to, "
        "m.active_state FROM placement p JOIN guild_member m USING (member_id) JOIN studio s USING (studio_id) "
        "JOIN endorsement e ON e.member_id = m.member_id JOIN craft c ON c.craft_code = e.craft_code "
        f"WHERE p.edition_code = ? AND p.approved = 1 AND s.district_id = ? AND m.active_state IN "
        f"({','.join('?' * len(states))}) ORDER BY c.label, m.invented_name", (edition, district, *states)).fetchall()
    con.close()
    return [Entry(*r) for r in rows]


def plan(district: str, edition: str, entries: list[Entry]) -> Plan:
    sections: dict[str, list[Entry]] = {}
    for e in entries:
        sections.setdefault(e.craft, []).append(e)
    p = Plan(district, edition, sorted(sections.items()))
    page = 2  # 0 cover, 1 contents
    for craft, items in p.sections:
        pages = []
        for i in range(0, len(items), ENTRIES_PER_PAGE):
            pages.append(page)
            for e in items[i:i + ENTRIES_PER_PAGE]:
                p.entry_page[_key(e)] = page
            page += 1
        p.section_pages[craft] = pages
    index_count = max(1, -(-len(entries) // INDEX_PER_PAGE))
    p.index_pages = list(range(page, page + index_count))
    p.page_count = page + index_count
    return p


def _footer(page, plan_: Plan, period: str, n: int) -> None:
    label = dict(DISTRICTS)[plan_.district]
    text = (f"DEMO / SYNTHETIC  |  {label}  |  {EDITIONS[plan_.edition]['label']} edition  |  {period}  |  "
            f"page {n + 1} of {plan_.page_count}")
    page.insert_text((M, H - 30), text, fontname="helv", fontsize=7.5, color=(0.35, 0.4, 0.47))


def _link(page, rect, target: int) -> None:
    page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": target, "to": pymupdf.Point(M, M)})


def render(snapshot: Path, district: str, edition: str, period: str, out: Path) -> Plan:
    entries = read_entries(snapshot, district, edition)
    p = plan(district, edition, entries)
    label = dict(DISTRICTS)[district]
    doc = pymupdf.open()
    for _ in range(p.page_count):
        doc.new_page(width=W, height=H)
    ink, muted, accent = (0.11, 0.15, 0.2), (0.35, 0.4, 0.47), (0.12, 0.35, 0.5)

    cover = doc[0]
    cover.draw_rect(pymupdf.Rect(0, 0, W, 230), color=None, fill=(0.93, 0.95, 0.97))
    cover.insert_text((M, 120), TITLE, fontname="hebo", fontsize=24, color=ink)
    cover.insert_text((M, 160), f"{label} Directory - {EDITIONS[edition]['label']} edition", fontname="helv",
                      fontsize=16, color=accent)
    cover.insert_text((M, 300), f"Period {period}.  {len(entries)} endorsed listings in {len(p.sections)} crafts.",
                      fontname="helv", fontsize=11, color=ink)
    cover.insert_text((M, 320), "Every person, studio and endorsement in this directory is invented.",
                      fontname="helv", fontsize=10, color=muted)

    contents = doc[1]
    contents.insert_text((M, 90), "Contents", fontname="hebo", fontsize=18, color=ink)
    y = 130
    lines = [(craft, p.section_pages[craft][0]) for craft, _ in p.sections] + [("Index", p.index_pages[0])]
    for text, target in lines:
        contents.insert_text((M, y), text, fontname="helv", fontsize=11, color=ink)
        dots = "." * max(3, 70 - len(text))
        contents.insert_text((M + 8 + len(text) * 5.6, y), dots, fontname="helv", fontsize=9, color=muted)
        contents.insert_text((W - M - 20, y), str(target + 1), fontname="helv", fontsize=11, color=ink)
        _link(contents, pymupdf.Rect(M, y - 11, W - M, y + 4), target)
        y += 22

    for craft, items in p.sections:
        for n, start in enumerate(range(0, len(items), ENTRIES_PER_PAGE)):
            page = doc[p.section_pages[craft][n]]
            page.insert_text((M, 80), craft + (" (continued)" if n else f"  -  {len(items)} listings"),
                             fontname="hebo", fontsize=15, color=accent)
            y = 115
            for e in items[start:start + ENTRIES_PER_PAGE]:
                page.insert_text((M, y), e.name, fontname="hebo", fontsize=10.5, color=ink)
                page.insert_text((M, y + 13), f"{e.studio}" + (f"  |  venue {e.venue}" if e.venue else ""),
                                 fontname="helv", fontsize=9, color=muted)
                if EDITIONS[edition]["detail"]:
                    extra = f"Endorsement {e.endorsement}, valid to {e.valid_to}"
                    if edition == "inspector":
                        extra += f"  |  member {e.member_id}  |  {e.state}"
                    page.insert_text((M, y + 25), extra, fontname="helv", fontsize=8.5, color=muted)
                y += 46

    index = sorted(entries, key=lambda e: (e.name, e.craft))
    for n, page_no in enumerate(p.index_pages):
        page = doc[page_no]
        page.insert_text((M, 80), "Index" + (" (continued)" if n else ""), fontname="hebo", fontsize=15, color=ink)
        y = 112
        for e in index[n * INDEX_PER_PAGE:(n + 1) * INDEX_PER_PAGE]:
            target = p.entry_page[_key(e)]
            page.insert_text((M, y), f"{e.name}  ({e.craft})", fontname="helv", fontsize=9.5, color=ink)
            page.insert_text((W - M - 20, y), str(target + 1), fontname="helv", fontsize=9.5, color=ink)
            _link(page, pymupdf.Rect(M, y - 9, W - M, y + 3), target)
            y += 15

    for n in range(p.page_count):
        _footer(doc[n], p, period, n)
    doc.set_toc([[1, "Cover", 1], [1, "Contents", 2]]
                + [[1, craft, p.section_pages[craft][0] + 1] for craft, _ in p.sections]
                + [[1, "Index", p.index_pages[0] + 1]])
    fixed = datetime(2026, 1, 1).strftime("D:%Y%m%d%H%M%S")
    doc.set_metadata({"title": f"{TITLE} - {label} - {EDITIONS[edition]['label']} - {period}",
                      "author": "CivicWorks demo", "subject": "DEMO / SYNTHETIC", "creationDate": fixed,
                      "modDate": fixed, "producer": "atlas-license-directory", "creator": "atlas"})
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out, garbage=3, deflate=True, no_new_id=True)
    doc.close()
    return p


def verify(path: Path, p: Plan) -> list[str]:
    """Open the finished PDF and check it the way a careful reader would. Returns the problems found."""
    problems = []
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - a file that will not open is a finding, not a crash
        return [f"cannot open: {exc.__class__.__name__}"]
    if doc.page_count != p.page_count:
        problems.append(f"{doc.page_count} pages, planned {p.page_count}")
    if TITLE not in doc[0].get_text():
        problems.append("cover does not carry the directory title")
    if not doc[doc.page_count - 1].get_text().lstrip().startswith("Index"):
        problems.append("the last page is not the index")
    links = doc[1].get_links()
    expected = [craft for craft, _ in p.sections] + ["Index"]
    if len(links) != len(expected):
        problems.append(f"contents has {len(links)} links, expected {len(expected)}")
    for link, title in zip(links, expected, strict=False):
        if link["page"] >= doc.page_count:
            problems.append(f"contents link for {title} points past the end of the file")
        elif not doc[link["page"]].get_text().lstrip().startswith(title):
            problems.append(f"contents link for {title} lands on a page that does not start with it")
    entries = {_key(e): e.name for _, items in p.sections for e in items}
    for n in p.index_pages:
        if n >= doc.page_count:
            problems.append(f"index page {n + 1} is missing")
            continue
        for link in doc[n].get_links():
            text = doc[n].get_textbox(link["from"]).strip()
            name = text.split("  (")[0].strip()
            if link["page"] >= doc.page_count:
                problems.append(f"index entry {name!r} points past the end of the file")
            elif name and name not in doc[link["page"]].get_text():
                problems.append(f"index entry '{name}' points to page {link['page'] + 1}, where it is not printed")
    toc = doc.get_toc()
    if len(toc) != len(expected) + 2:
        problems.append(f"{len(toc)} bookmarks, expected {len(expected) + 2}")
    for n in range(doc.page_count):
        if f"page {n + 1} of {p.page_count}" not in doc[n].get_text():
            problems.append(f"page {n + 1} footer is wrong")
            break
    if "SYNTHETIC" not in (doc.metadata or {}).get("subject", ""):
        problems.append("metadata does not mark the file synthetic")
    if len(entries) != sum(len(items) for _, items in p.sections):
        problems.append("duplicate entries in the plan")
    doc.close()
    return problems
