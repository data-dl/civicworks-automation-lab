"""The quarterly workbooks. Totals are live Excel formulas over the venue rows, not pasted numbers, so a
reader can trace every figure on the Summary tab back to the venue that reported it."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .runkit import SYNTHETIC_NOTICE

HEAD = PatternFill("solid", fgColor="1F4E5F")
HEAD_FONT = Font(bold=True, color="FFFFFF")
DRAFT_FILL = PatternFill("solid", fgColor="FFF2CC")
APPROVED_FILL = PatternFill("solid", fgColor="E2F0D9")
FLAG_FILL = PatternFill("solid", fgColor="F8CBAD")
FIXED_TIME = datetime(2026, 1, 1)


def _header(ws, row: int, labels: list[str]) -> None:
    for col, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=col, value=label)
        cell.fill, cell.font = HEAD, HEAD_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 30


def _widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _about(wb: Workbook, ctx: dict, title: str) -> None:
    ws = wb.active
    ws.title = "About"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    rows = [("Quarter", ctx["quarter"]), ("Compared with", ctx["prior"]), ("Status", ctx["status"]),
            ("Notice", SYNTHETIC_NOTICE), ("Produced by", "regional-programs-analytics")]
    for i, (k, v) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws["B5"].fill = APPROVED_FILL if ctx["status"] == "APPROVED" else DRAFT_FILL
    _widths(ws, [16, 70])


def _qa(wb: Workbook, ctx: dict) -> None:
    ws = wb.create_sheet("QA Checks")
    _header(ws, 1, ["Severity", "Rule", "Detail"])
    for i, f in enumerate(ctx["findings"], start=2):
        ws.cell(row=i, column=1, value=f["severity"])
        ws.cell(row=i, column=2, value=f["rule"])
        ws.cell(row=i, column=3, value=f["detail"])
        if f["severity"] == "blocking":
            for c in range(1, 4):
                ws.cell(row=i, column=c).fill = FLAG_FILL
    if not ctx["findings"]:
        ws["A2"] = "none"
    _widths(ws, [11, 24, 100])


def _finish(wb: Workbook, path: Path) -> Path:
    wb.properties.creator = "CivicWorks demo"
    wb.properties.created = wb.properties.modified = FIXED_TIME
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def build_tier_workbook(path: Path, tier: str, ctx: dict) -> Path:
    wb = Workbook()
    _about(wb, ctx, f"Harbor Arts Network - {tier.title()} programs, {ctx['quarter']}")

    venue = wb.create_sheet("By Venue")
    cols = ["Venue ID", "Venue", "Region", "Sessions", "Attendance", "First-time visitors", "Complaints",
            "Improvements"]
    _header(venue, 1, cols)
    ids = sorted(v for v, d in ctx["venues"].items() if d["tier"] == tier)
    for r, venue_id in enumerate(ids, start=2):
        d = ctx["venues"][venue_id]
        fig = ctx["current"].get(venue_id)
        venue.cell(row=r, column=1, value=venue_id)
        venue.cell(row=r, column=2, value=d["name"])
        venue.cell(row=r, column=3, value=ctx["regions"][d["region_code"]])
        if fig is None:
            venue.cell(row=r, column=4, value="NO SUBMISSION").fill = FLAG_FILL
            continue
        for c, key in enumerate(["sessions_delivered", "attendance", "first_time_visitors", "complaints",
                                 "improvements_logged"], start=4):
            venue.cell(row=r, column=c, value=fig.get(key, 0))
    last = len(ids) + 1
    _widths(venue, [10, 28, 12, 10, 12, 12, 11, 13])

    region = wb.create_sheet("By Region")
    _header(region, 1, ["Region", "Sessions", "Attendance", "First-time visitors", "Complaints"])
    for r, label in enumerate(ctx["regions"].values(), start=2):
        region.cell(row=r, column=1, value=label)
        for c, src in enumerate(["D", "E", "F", "G"], start=2):
            region.cell(row=r, column=c,
                        value=f"=SUMIFS('By Venue'!{src}$2:{src}${last},'By Venue'!$C$2:$C${last},$A{r})")
    _widths(region, [14, 10, 12, 14, 11])

    summary = wb.create_sheet("Summary", 1)
    summary["A1"] = f"{tier.title()} programs - {ctx['quarter']} ({ctx['status']})"
    summary["A1"].font = Font(bold=True, size=13)
    kpis = [("Sessions delivered", f"=SUM('By Venue'!D2:D{last})"),
            ("Attendance", f"=SUM('By Venue'!E2:E{last})"),
            ("First-time visitors", f"=SUM('By Venue'!F2:F{last})"),
            ("Attendance per session", "=IFERROR(ROUND(B4/B3,1),0)"),
            ("Complaints per 1,000 visits", f"=IFERROR(ROUND(SUM('By Venue'!G2:G{last})/B4*1000,1),0)"),
            ("Venues reporting", f"=COUNT('By Venue'!E2:E{last})&\" of {len(ids)}\"")]
    for i, (label, formula) in enumerate(kpis, start=3):
        summary.cell(row=i, column=1, value=label).font = Font(bold=True)
        summary.cell(row=i, column=2, value=formula)
    _widths(summary, [28, 16])
    chart = BarChart()
    chart.title = "Attendance by region (visits)"
    chart.add_data(Reference(region, min_col=3, min_row=1, max_row=5), titles_from_data=True)
    chart.set_categories(Reference(region, min_col=1, min_row=2, max_row=5))
    chart.height, chart.width, chart.legend = 7, 14, None
    chart.x_axis.delete = chart.y_axis.delete = False  # openpyxl hides both axes unless told otherwise
    chart.y_axis.majorGridlines = None
    summary.add_chart(chart, "D3")

    comp = wb.create_sheet("Quarter Comparison")
    _header(comp, 1, ["Region", f"Attendance {ctx['prior']}", f"Attendance {ctx['quarter']}", "Change", "Flag"])
    rows = [c for c in ctx["comparison"] if c["tier"] == tier]
    for r, c in enumerate(rows, start=2):
        comp.cell(row=r, column=1, value=c["region"])
        comp.cell(row=r, column=2, value=c["prior"] or None)
        comp.cell(row=r, column=3, value=c["current"])
        cell = comp.cell(row=r, column=4, value=f"=IF(B{r}>0,C{r}/B{r}-1,\"n/a\")")
        cell.number_format = "+0%;-0%;0%"
        comp.cell(row=r, column=5, value=c["flag"])
        if c["flag"] == "needs commentary":
            comp.cell(row=r, column=5).fill = FLAG_FILL
    _widths(comp, [14, 18, 18, 10, 18])
    _qa(wb, ctx)
    return _finish(wb, path)


def build_incident_workbook(path: Path, ctx: dict) -> Path:
    wb = Workbook()
    _about(wb, ctx, f"Harbor Arts Network - incident summary, {ctx['quarter']}")
    ws = wb.create_sheet("Incidents")
    _header(ws, 1, ["Venue ID", "Venue", "Region", "Tier", "Minor", "Reportable", "Total"])
    ids = sorted(ctx["venues"])
    for r, venue_id in enumerate(ids, start=2):
        d, fig = ctx["venues"][venue_id], ctx["current"].get(venue_id)
        ws.cell(row=r, column=1, value=venue_id)
        ws.cell(row=r, column=2, value=d["name"])
        ws.cell(row=r, column=3, value=ctx["regions"][d["region_code"]])
        ws.cell(row=r, column=4, value=d["tier"])
        if fig is None:
            ws.cell(row=r, column=5, value="NO SUBMISSION").fill = FLAG_FILL
            continue
        ws.cell(row=r, column=5, value=fig.get("incidents_minor", 0))
        ws.cell(row=r, column=6, value=fig.get("incidents_reportable", 0))
        ws.cell(row=r, column=7, value=f"=E{r}+F{r}")
        if fig.get("incidents_reportable", 0):
            ws.cell(row=r, column=6).fill = FLAG_FILL
    last = len(ids) + 1
    ws.cell(row=last + 1, column=4, value="Total").font = Font(bold=True)
    for col in "EFG":
        ws[f"{col}{last + 1}"] = f"=SUM({col}2:{col}{last})"
        ws[f"{col}{last + 1}"].font = Font(bold=True)
    _widths(ws, [10, 28, 12, 10, 8, 11, 8])
    _qa(wb, ctx)
    return _finish(wb, path)
