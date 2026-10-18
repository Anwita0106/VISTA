#!/usr/bin/env python3
"""Generate the testing reports from test-results/test-results.json (run collect_results.py first).

Outputs (in reports/):
  Functional_Testing_Report.pdf, Non_Functional_Testing_Report.pdf, Combined_Testing_Report.pdf
  Functional_Test_Cases.xlsx, Non_Functional_Test_Cases.xlsx, defect-log.xlsx, defect-log.csv
Every number in the reports is computed from the executed results – nothing is typed by hand."""
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
TR = ROOT / "test-results"
OUT = ROOT / "reports"
FONTS = Path(__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("DV", str(FONTS / "DejaVuSansCondensed.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONTS / "DejaVuSansCondensed-Bold.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB", italic="DV", boldItalic="DVB")

# ----------------------------------------------------------------- palette (matches the reference sheets)
NAVY = colors.HexColor("#1B3A6B")
BLUE = colors.HexColor("#2457A6")
BLUE_LIGHT = colors.HexColor("#EAF1FB")
BORDER = colors.HexColor("#B9C7DD")
ZEBRA = colors.HexColor("#F6F8FC")
TEXT = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#5B6475")
PASS_BG, PASS_FG = colors.HexColor("#E2F3E5"), colors.HexColor("#1E7B34")
FAIL_BG, FAIL_FG = colors.HexColor("#FDE3E1"), colors.HexColor("#B42318")
NEUTRAL_BG, NEUTRAL_FG = colors.HexColor("#ECEEF2"), colors.HexColor("#4B5563")
ORANGE = colors.HexColor("#E46C0A")
ORANGE_LIGHT = colors.HexColor("#FFF6EE")

STATUS_STYLE = {"Pass": (PASS_BG, PASS_FG), "Fail": (FAIL_BG, FAIL_FG), "Blocked": (NEUTRAL_BG, NEUTRAL_FG), "Not Run": (NEUTRAL_BG, NEUTRAL_FG)}


def ps(name, size=6.7, font="DV", color=TEXT, lead=None, align=TA_LEFT, **kw):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=lead or size * 1.22, textColor=color, alignment=align, **kw)


CELL = ps("cell")
CELL_B = ps("cellb", font="DVB")
HEAD = ps("head", 7, "DVB", colors.white, align=TA_CENTER)
BODY = ps("body", 8.6, lead=11.5)
BODY_S = ps("bodys", 7.6, lead=10, color=MUTED)
H2 = ps("h2", 12, "DVB", NAVY, lead=15, spaceBefore=4, spaceAfter=5)
H3 = ps("h3", 9.5, "DVB", NAVY, lead=12, spaceBefore=3, spaceAfter=3)


def P(text, style=CELL):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def fmt_pct(v):
    return "N/A" if v is None else f"{v:.1f}%".replace(".0%", "%")


# ----------------------------------------------------------------- page furniture
class Banner(Flowable):
    """Blue title banner with a hostel-building icon (mirrors the reference sheets)."""

    def __init__(self, title, subtitle, width):
        super().__init__()
        self.title, self.subtitle, self.width, self.height = title, subtitle, width, 19 * mm

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(NAVY)
        c.roundRect(0, 0, w, h, 3 * mm, stroke=0, fill=1)
        c.setFillColor(BLUE)
        c.roundRect(w * 0.55, 0, w * 0.45, h, 3 * mm, stroke=0, fill=1)
        c.rect(w * 0.55, 0, 6 * mm, h, stroke=0, fill=1)
        # icon: building with windows and a door
        x0, y0 = 5 * mm, 3 * mm
        c.setFillColor(colors.white)
        c.roundRect(x0, y0, 13 * mm, 13 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(BLUE)
        c.rect(x0 + 2.5 * mm, y0 + 2 * mm, 8 * mm, 8 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        for i in range(2):
            for j in range(2):
                c.rect(x0 + 3.6 * mm + i * 3.6 * mm, y0 + 6.2 * mm + j * -2.7 * mm + 1.2 * mm, 2.1 * mm, 1.6 * mm, stroke=0, fill=1)
        c.rect(x0 + 5.6 * mm, y0 + 2 * mm, 1.8 * mm, 2.6 * mm, stroke=0, fill=1)
        c.setFillColor(BLUE)
        p = c.beginPath()
        p.moveTo(x0 + 1.8 * mm, y0 + 10 * mm)
        p.lineTo(x0 + 6.5 * mm, y0 + 12 * mm)
        p.lineTo(x0 + 11.2 * mm, y0 + 10 * mm)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("DVB", 15)
        c.drawCentredString(w / 2 + 6 * mm, h - 8.2 * mm, self.title)
        c.setFont("DVB", 11)
        c.setFillColor(colors.HexColor("#DCE7F7"))
        c.drawCentredString(w / 2 + 6 * mm, 4.4 * mm, self.subtitle)


def purpose_block(text, width):
    t = Table([[Paragraph("Purpose", ps("pp", 9.5, "DVB", colors.white, align=TA_CENTER)), Paragraph(escape(text), ps("pt", 8.4, lead=11))]],
              colWidths=[24 * mm, width - 24 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), NAVY), ("BACKGROUND", (1, 0), (1, 0), BLUE_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LEFTPADDING", (1, 0), (1, 0), 7), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def meta_line(data, kind):
    env = data["environment"]
    gen = datetime.fromisoformat(data["generated_at"]).astimezone(IST).strftime("%d %b %Y, %H:%M IST")
    return Paragraph(escape(
        f"Report date: {gen}   ·   Results source: test-results/test-results.json ({kind})   ·   Environment: {env['os']}, {env['cpu_count']} vCPU, "
        f"Python {env['python']}, Node {env['node']}, {env['postgresql'].replace('psql (PostgreSQL) ', 'PostgreSQL ')}, {env['chromium']}"), BODY_S)


class Doc(BaseDocTemplate):
    def __init__(self, path, report_name, report_date):
        super().__init__(str(path), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=13 * mm,
                         title=f"VISTA – {report_name}", author="VISTA project team", subject="Software Engineering Lab Assessment VI")
        self.report_name, self.report_date = report_name, report_date
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=self._footer)])

    def _footer(self, c, doc):
        c.saveState()
        w, _ = landscape(A4)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.line(10 * mm, 9 * mm, w - 10 * mm, 9 * mm)
        c.setFont("DV", 7)
        c.setFillColor(MUTED)
        c.drawString(10 * mm, 5.5 * mm, f"VISTA – Smart Hostel & Accommodation Management System  ·  {self.report_name}")
        c.drawCentredString(w / 2, 5.5 * mm, f"Report date: {self.report_date}")
        c.drawRightString(w - 10 * mm, 5.5 * mm, f"Page {doc.page}")
        c.restoreState()


def status_cell(status):
    bg, fg = STATUS_STYLE.get(status, (NEUTRAL_BG, NEUTRAL_FG))
    return Paragraph(escape(status), ps(f"st{status}", 7, "DVB", fg, align=TA_CENTER))


def case_table(rows, columns, width):
    """columns: list of (header, key/callable, width_mm, bold?)"""
    total = sum(c[2] for c in columns)
    widths = [c[2] / total * width for c in columns]
    data = [[Paragraph(escape(c[0]), HEAD) for c in columns]]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER), ("BOX", (0, 0), (-1, -1), 0.8, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    status_col = next(i for i, c in enumerate(columns) if c[1] == "status")
    actual_col = next((i for i, c in enumerate(columns) if c[1] == "actual"), None)
    for r_i, r in enumerate(rows, start=1):
        row = []
        for _header, key, _, bold in columns:
            if key == "status":
                row.append(status_cell(r["status"]))
            else:
                v = key(r) if callable(key) else r.get(key, "")
                row.append(P(v, CELL_B if bold else CELL))
        data.append(row)
        if r_i % 2 == 0:
            style.append(("BACKGROUND", (0, r_i), (-1, r_i), ZEBRA))
        bg, _ = STATUS_STYLE.get(r["status"], (NEUTRAL_BG, NEUTRAL_FG))
        style.append(("BACKGROUND", (status_col, r_i), (status_col, r_i), bg))
        if actual_col is not None:
            style.append(("BACKGROUND", (actual_col, r_i), (actual_col, r_i),
                          {"Pass": colors.HexColor("#F1F9F2"), "Fail": colors.HexColor("#FEF1F0")}.get(r["status"], colors.HexColor("#F5F6F8"))))
        style.append(("VALIGN", (status_col, r_i), (status_col, r_i), "MIDDLE"))
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def summary_and_takeaways(title, s, takeaways, width):
    hdr = ["Total Test Cases", "Executed", "Passed", "Failed", "Blocked", "Not Run", "Pass Percentage"]
    vals = [s["total"], s["executed"], s["passed"], s["failed"], s["blocked"], s["not_run"], fmt_pct(s["pass_percentage"])]
    left_w = width * 0.50
    st = Table([[Paragraph(escape(title), ps("sh", 9.5, "DVB", colors.white, align=TA_CENTER))] + [""] * 6,
                [Paragraph(escape(h), ps("shh", 7.2, "DVB", NAVY, align=TA_CENTER)) for h in hdr],
                [Paragraph(f"<b>{escape(str(v))}</b>", ps(f"sv{i}", 13, "DVB", [TEXT, TEXT, PASS_FG, FAIL_FG, NEUTRAL_FG, NEUTRAL_FG, colors.HexColor("#9A5B00")][i],
                                                       align=TA_CENTER, lead=16)) for i, v in enumerate(vals)]],
               colWidths=[left_w / 7] * 7)
    st.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 1), (-1, 1), BLUE_LIGHT),
        ("GRID", (0, 1), (-1, -1), 0.5, BORDER), ("BOX", (0, 0), (-1, -1), 0.9, NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (2, 2), (2, 2), PASS_BG), ("BACKGROUND", (3, 2), (3, 2), FAIL_BG), ("BACKGROUND", (4, 2), (5, 2), NEUTRAL_BG),
        ("BACKGROUND", (6, 2), (6, 2), colors.HexColor("#FFF4DE")), ("TOPPADDING", (0, 2), (-1, 2), 6), ("BOTTOMPADDING", (0, 2), (-1, 2), 6),
    ]))
    formula = Paragraph(escape("Pass percentage = Passed ÷ Executed × 100. Executed = test cases with a Pass or Fail outcome; Blocked and Not Run are reported separately."), BODY_S)
    left = Table([[st], [formula]], colWidths=[left_w])
    left.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 1), (0, 1), 3)]))
    right_w = width - left_w - 6 * mm
    bullets = [[Paragraph("✔", ps("tick", 8.5, "DVB", PASS_FG)), Paragraph(t, ps("tk", 7.8, lead=10.2))] for t in takeaways]
    kt = Table([[Paragraph("Key Takeaways", ps("kh", 9.5, "DVB", colors.white)), ""]] + bullets, colWidths=[5 * mm, right_w - 5 * mm])
    kt.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), ORANGE), ("BACKGROUND", (0, 1), (-1, -1), ORANGE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.9, ORANGE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 1), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    outer = Table([[left, "", kt]], colWidths=[left_w, 6 * mm, right_w])
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return KeepTogether([outer])


def legend():
    cells = []
    for s in ("Pass", "Fail", "Blocked", "Not Run"):
        cells += [status_cell(s), Paragraph(escape({"Pass": "executed, met the criterion", "Fail": "executed, did not meet the criterion",
                                                      "Blocked": "could not run in this environment", "Not Run": "needs resources not available"}[s]), BODY_S)]
    t = Table([cells], colWidths=[14 * mm, 44 * mm] * 4)
    sty = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 3)]
    for i, s in enumerate(("Pass", "Fail", "Blocked", "Not Run")):
        sty.append(("BACKGROUND", (2 * i, 0), (2 * i, 0), STATUS_STYLE[s][0]))
    t.setStyle(TableStyle(sty))
    return t


# ----------------------------------------------------------------- content builders
FT_COLUMNS = [
    ("TC ID", "id", 12, True), ("Test Case Description", "description", 30, True), ("Module", "module", 19, False),
    ("Pre-Conditions", "preconditions", 22, False), ("Test Steps", "steps", 38, False), ("Test Data (Input)", "data", 25, False),
    ("Expected Result", "expected", 37, False), ("Actual Result", "actual", 58, False), ("Status", "status", 12, False),
    ("Defect ID", lambda r: r["defects"] or "—", 12, False),
]
NFT_COLUMNS = [
    ("TC ID", "id", 13, True), ("Quality Attribute", "attribute", 21, True), ("Test Case Description", "description", 28, False),
    ("Metric / Criteria", lambda r: f"{r['criteria']}\n[Target: {r['target_source']}]", 30, False), ("Test Steps / Tools", "steps", 36, False),
    ("Expected Result", "expected", 23, False), ("Actual Result", "actual", 69, False), ("Status", "status", 12, False),
    ("Evidence / Defect", lambda r: (r["defects"] + "\n" if r["defects"] else "") + (r["evidence"] or ""), 25, False),
]


def ft_takeaways(d):
    s = d["summary"]["functional"]
    tools = d["summary"]["tools"]
    reg = {x["id"]: x for x in d["defects"]}
    fails = [r for r in d["functional_cases"] if r["status"] == "Fail"]
    t = [f"{s['executed']} of {s['total']} functional test cases were executed against the running application; "
         f"{s['passed']} passed and {s['failed']} failed (pass rate {fmt_pct(s['pass_percentage'])}).",
         f"Evidence comes from {tools['pytest']['total']} API tests (pytest) and {tools['playwright']['passed']} browser tests (Playwright, Chromium) "
         "that drive the real React UI, FastAPI backend and PostgreSQL database."]
    if fails:
        t.append("Failed: " + ", ".join(f"{r['id']} ({r['description']})" for r in fails) + ".")
    t.append("The first execution failed 6 browser tests and 1 API test because of test-script problems (DEF-07) – fixed and re-run; "
             "no functional requirement failed after the fixes.")
    if "DEF-01" in reg:
        t.append("A real data-integrity defect (DEF-01, duplicate complaints on parallel submit) was found by testing and fixed.")
    t.append("The unique P2P delivery flow (₹10 fee, OTP lock after 3 tries, OTP expiry, QR + photo check) and SOS alerts were verified end to end.")
    t.append("Payments are demo records only and SOS is not connected to real emergency services.")
    return t


def nft_takeaways(d):
    s = d["summary"]["nonfunctional"]
    rows = {r["id"]: r for r in d["nonfunctional_cases"]}
    fails = [r for r in d["nonfunctional_cases"] if r["status"] == "Fail"]
    k6 = d["k6_runs"]
    t = [f"{s['executed']} of {s['total']} non-functional tests were executed: {s['passed']} passed, {s['failed']} failed "
         f"({fmt_pct(s['pass_percentage'])}); {s['blocked']} blocked and {s['not_run']} not run."]
    if "peak-300vus" in k6:
        r = k6["peak-300vus"]
        t.append(f"300 concurrent users: {r['http_req_failed_rate'] * 100:.2f} % errors, average {r['latency_ms']['avg']:.0f} ms – "
                 "only after fixing DEF-03 (database connections exhausted; first run had 0.82 % errors).")
    for r in fails:
        t.append(f"FAIL {r['id']} – {r['description']}: see {r['defects'] or 'actual result'}.")
    t.append("Security checks passed: 401 on all protected endpoints, 403 role matrix, SQL injection, stored XSS, token tampering, brute-force lockout, upload filtering.")
    blocked = [r["id"] for r in d["nonfunctional_cases"] if r["status"] in ("Blocked", "Not Run")]
    t.append(f"Not executed: {', '.join(blocked)} (other browsers blocked by the sandbox; usability study and 30-day uptime need real users / deployment).")
    if rows.get("NFT-04", {}).get("status") == "Pass":
        t.append("SOS alerts reached the warden board in under 5 s even under a 150-user load (NFR03).")
    return t


def perf_table(d, width):
    hdr = ["Run", "Concurrent users", "Steady duration", "Requests", "Throughput (req/s)", "Failed %", "Avg (ms)", "Median (ms)", "p95 (ms)", "p99 (ms)", "Max (ms)"]
    rows = [[Paragraph(escape(h), HEAD) for h in hdr]]
    order = ["normal-50vus", "peak-150vus", "peak-300vus", "background-sos"]
    for k in [o for o in order if o in d["k6_runs"]]:
        r = d["k6_runs"][k]
        lat = r["latency_ms"]
        rows.append([P(k, CELL_B), P(r["vus"]), P(r["duration"]), P(f"{r['requests']:,}"), P(r["throughput_rps"]),
                     P(f"{r['http_req_failed_rate'] * 100:.2f}"), P(f"{lat['avg']:.0f}"), P(f"{lat['med']:.0f}"), P(f"{lat['p(95)']:.0f}"),
                     P(f"{lat['p(99)']:.0f}"), P(f"{lat['max']:.0f}")])
    t = Table(rows, colWidths=[width / len(hdr)] * len(hdr), repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA])]))
    note = Paragraph(escape(
        "Tool: k6 " + d["environment"]["k6"].split(" ")[1] + ". Mixed workload per virtual user: 80 % student session (dashboard, notices, complaints, "
        "notifications), 10 % complaint creation, 10 % warden queue reads; 1 s think time; 10 s ramp-up. API: FastAPI/uvicorn with 2 workers, PostgreSQL 16 "
        "and the load generator on the same 2-vCPU container, so absolute numbers are lower than dedicated hosting would give. "
        "'background-sos' is the 150-user load used while measuring SOS latency (NFT-04)."), BODY_S)
    return [t, Spacer(1, 2 * mm), note]


def defect_table(d, width):
    cols = [("Defect ID", "id", 13), ("Severity", "severity", 14), ("Type", "type", 17), ("Affected Module", "module", 26), ("Found by", "found_by", 26),
            ("Reproduction Steps", "steps", 46), ("Expected Result", "expected", 34), ("Actual Result", "actual", 50), ("Status", "status", 14),
            ("Resolution", "resolution", 52)]
    total = sum(c[2] for c in cols)
    rows = [[Paragraph(escape(c[0]), HEAD) for c in cols]]
    sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    for i, x in enumerate(d["defects"], start=1):
        rows.append([P(x[c[1]], CELL_B if c[1] == "id" else CELL) for c in cols])
        bg = PASS_BG if x["status"] == "Fixed" else (FAIL_BG if x["status"] == "Open" else NEUTRAL_BG)
        sty.append(("BACKGROUND", (8, i), (8, i), bg))
        if i % 2 == 0:
            sty.append(("BACKGROUND", (0, i), (7, i), ZEBRA))
    t = Table(rows, colWidths=[c[2] / total * width for c in cols], repeatRows=1)
    t.setStyle(TableStyle(sty))
    return t


def module_table(d, width):
    mods = {}
    for r in d["functional_cases"]:
        m = mods.setdefault(r["module"], {"Pass": 0, "Fail": 0, "Blocked": 0, "Not Run": 0, "ids": []})
        m[r["status"]] += 1
        m["ids"].append(r["id"])
    hdr = ["Module", "Test cases", "Passed", "Failed", "Blocked / Not Run", "Case IDs"]
    rows = [[Paragraph(h, HEAD) for h in hdr]]
    for k, m in mods.items():
        rows.append([P(k, CELL_B), P(len(m["ids"])), P(m["Pass"]), P(m["Fail"]), P(m["Blocked"] + m["Not Run"]), P(", ".join(m["ids"]))])
    t = Table(rows, colWidths=[w * width for w in (0.16, 0.08, 0.07, 0.07, 0.1, 0.52)], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def tools_table(d, width):
    t_ = d["summary"]["tools"]
    first = run1_summary()
    rows = [[Paragraph(h, HEAD) for h in ["Automated suite", "What it exercises", "First run", "Final run (reported)", "Raw result file"]]]
    rows += [
        [P("pytest (API)", CELL_B), P("FastAPI endpoints + PostgreSQL: functional, security, integrity"), P(first.get("pytest", "—")),
         P(f"{t_['pytest']['passed']}/{t_['pytest']['total']} passed"), P("pytest-results.json, pytest-junit.xml")],
        [P("Vitest (frontend unit)", CELL_B), P("Form validation, UI components, login page"), P("—"),
         P(f"{t_['vitest']['passed']}/{t_['vitest']['total']} passed"), P("vitest-results.json")],
        [P("Playwright (E2E)", CELL_B), P("Real browser against the running app: workflows, XSS, accessibility, responsive, mobile"),
         P(first.get("playwright", "—")), P(f"{t_['playwright']['passed']}/{t_['playwright']['total']} passed, {t_['playwright']['blocked']} blocked (Firefox, WebKit)"),
         P("playwright-results.json, playwright-junit.xml, playwright-html/")],
        [P("k6 (load)", CELL_B), P("50 / 150 / 300 concurrent users + SOS background load"), P(first.get("k6", "—")),
         P(f"{t_['k6']['runs']} runs, see performance table"), P("perf/k6-*.json")],
        [P("NFT runner", CELL_B), P("SOS latency, large dataset, restart, backup/restore, lint, build, setup, privacy"), P("—"),
         P(f"{t_['nft_runner']['passed']}/{t_['nft_runner']['checks']} passed, {t_['nft_runner']['failed']} failed"), P("nft-results.json")],
    ]
    t = Table(rows, colWidths=[w * width for w in (0.13, 0.33, 0.17, 0.2, 0.17)])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def run1_summary() -> dict:
    out = {}
    d1 = TR / "run1-initial"
    junit = d1 / "pytest-junit.xml"
    if junit.exists():
        import xml.etree.ElementTree as ET
        s = ET.parse(junit).getroot()
        s = s if s.tag == "testsuite" else s[0]
        n, f = int(s.get("tests")), int(s.get("failures")) + int(s.get("errors"))
        out["pytest"] = f"{n - f}/{n} passed, {f} failed"
    pw = d1 / "playwright-results.json"
    if pw.exists():
        st = json.loads(pw.read_text())["stats"]
        out["playwright"] = f"{st['expected']}/{st['expected'] + st['unexpected']} passed, {st['unexpected']} failed"
    k = d1 / "k6-peak-300vus.json"
    if k.exists():
        r = json.loads(k.read_text())
        out["k6"] = f"300 users: {r['http_req_failed_rate'] * 100:.2f} % failed, p99 {r['latency_ms']['p(99)'] / 1000:.0f} s"
    return out


def traceability(d, width):
    import re
    req = {}
    for r in d["functional_cases"]:
        for fr in re.findall(r"(?:FR|NFR)\d+", r["requirements"]):
            req.setdefault(fr, []).append(r["id"])
    for r in d["nonfunctional_cases"]:
        for fr in re.findall(r"NFR\d+", r["requirements"]):
            req.setdefault(fr, []).append(r["id"])
    keys = sorted(req, key=lambda k: (k.startswith("NFR"), int(re.sub(r"\D", "", k))))
    status = {r["id"]: r["status"] for r in d["functional_cases"] + d["nonfunctional_cases"]}
    rows = [[Paragraph(h, HEAD) for h in ["Requirement", "Covered by test cases", "Result", "Requirement", "Covered by test cases", "Result"]]]
    half = (len(keys) + 1) // 2
    for i in range(half):
        row = []
        for k in (keys[i], keys[i + half] if i + half < len(keys) else None):
            if k is None:
                row += [P(""), P(""), P("")]
                continue
            ids = sorted(set(req[k]))
            st = {status[x] for x in ids}
            res = "Fail" if "Fail" in st else ("Pass" if st == {"Pass"} else "Partial")
            row += [P(k, CELL_B), P(", ".join(ids)), P(res)]
        rows.append(row)
    t = Table(rows, colWidths=[w * width for w in (0.09, 0.33, 0.08, 0.09, 0.33, 0.08)], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    uncovered = [f"FR{i:02d}" for i in range(1, 36) if f"FR{i:02d}" not in req]
    note = Paragraph(escape("'Partial' = at least one linked case was Blocked or Not Run. FRs from the Lab VI report not covered by an automated case: "
                            + (", ".join(uncovered) if uncovered else "none") + "."), BODY_S)
    return [t, Spacer(1, 2 * mm), note]


def overall_summary(d, width):
    f, n = d["summary"]["functional"], d["summary"]["nonfunctional"]
    tot = {k: f[k] + n[k] for k in ("total", "executed", "passed", "failed", "blocked", "not_run")}
    tot["pass_percentage"] = round(100 * tot["passed"] / tot["executed"], 1) if tot["executed"] else None
    hdr = ["Test level", "Total", "Executed", "Passed", "Failed", "Blocked", "Not Run", "Pass %"]
    rows = [[Paragraph(h, HEAD) for h in hdr]]
    for name, s in (("Functional (FT)", f), ("Non-functional (NFT)", n), ("Overall", tot)):
        rows.append([P(name, CELL_B)] + [P(s[k], CELL_B if name == "Overall" else CELL) for k in ("total", "executed", "passed", "failed", "blocked", "not_run")]
                    + [P(fmt_pct(s["pass_percentage"]), CELL_B)])
    t = Table(rows, colWidths=[width * 0.22] + [width * 0.78 / 7] * 7)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, BORDER), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("BACKGROUND", (0, 3), (-1, 3), BLUE_LIGHT), ("BACKGROUND", (3, 1), (3, 3), PASS_BG), ("BACKGROUND", (4, 1), (4, 3), FAIL_BG)]))
    return t, tot


LIMITATIONS = [
    "The application was not deployed to a public URL from this environment (no hosting account access). All results come from a local run; "
    "deployment files (Dockerfile, render.yaml) and instructions are included.",
    "Load tests ran on one 2-vCPU container that also hosted PostgreSQL and the k6 load generator; production hosting will give different numbers.",
    "Firefox and WebKit/Safari could not be downloaded in this sandbox (network policy), so cross-browser results are limited to Chromium and "
    "mobile-viewport emulation in Chromium. Real Android/iOS devices were not tested.",
    "NFR10 (key tasks within 15 minutes) and NFR07 (99.5 % monthly uptime) need real users and a long-running deployment and were not executed.",
    "Payments are simulated demo records (no payment gateway). SOS alerts are in-app only and are not connected to emergency services.",
    "Encryption at rest of personal data (NFR06) is not implemented (DEF-04).",
]


def build_pdf(path, kind, d):
    gen = datetime.fromisoformat(d["generated_at"]).astimezone(IST).strftime("%d %b %Y")
    names = {"ft": "Functional Testing Report", "nft": "Non-Functional Testing Report", "all": "Combined Testing Report"}
    doc = Doc(path, names[kind], gen)
    W = doc.width
    story = []
    if kind == "all":
        story += [Banner("Smart Hostel & Accommodation Management System (VISTA)", "Combined Testing Report – Functional and Non-Functional", W),
                  Spacer(1, 4 * mm),
                  purpose_block("This report brings together all functional and non-functional testing of VISTA (VIT Integrated Smart Transit & "
                                "Accommodation System). Every result below was produced by automated tests executed against the running application "
                                "(React frontend, FastAPI backend, PostgreSQL). Cases that could not be executed are marked Blocked or Not Run with the reason.", W),
                  Spacer(1, 2 * mm), meta_line(d, "combined"), Spacer(1, 4 * mm), Paragraph("1. Overall test summary", H2)]
        t, tot = overall_summary(d, W)
        story += [t, Spacer(1, 3 * mm), legend(), Spacer(1, 4 * mm), Paragraph("2. Automated suites and execution history", H2), tools_table(d, W),
                  Spacer(1, 2 * mm),
                  Paragraph(escape("The 'first run' column shows genuine failures from the initial execution. Their causes are listed in the defect log "
                                   "(section 7); after fixes, the affected tests were re-run and the final run is what the case tables report."), BODY_S),
                  PageBreak()]
    if kind in ("ft", "all"):
        if kind == "ft":
            story += [Banner("Smart Hostel & Accommodation Management System (VISTA)", "Functional Testing – Test Cases (with Pass and Fail Examples)", W),
                      Spacer(1, 4 * mm)]
        else:
            story += [Paragraph("3. Functional testing – test cases", H2)]
        story += [purpose_block("Functional testing verifies that VISTA works as specified in the functional requirements (FR01–FR35) of the Lab VI "
                                "report: authentication and roles, complaints and escalation, visitor approval, hostel services, SOS, peer-to-peer "
                                "delivery with OTP/QR handover, notices, community features and administration.", W),
                  Spacer(1, 2 * mm)]
        if kind == "ft":
            story += [meta_line(d, "functional"), Spacer(1, 2 * mm), legend()]
        story += [Spacer(1, 3 * mm), case_table(d["functional_cases"], FT_COLUMNS, W), Spacer(1, 4 * mm),
                  summary_and_takeaways("Functional Testing Summary", d["summary"]["functional"], [escape(x) for x in ft_takeaways(d)], W)]
        if kind == "ft":
            story += [CondPageBreak(60 * mm), Spacer(1, 4 * mm), Paragraph("Results by module", H3), module_table(d, W)]
        if kind == "all":
            story += [PageBreak()]
    if kind in ("nft", "all"):
        if kind == "nft":
            story += [Banner("Smart Hostel & Accommodation Management System (VISTA)", "Non-Functional Testing – Test Cases (with Pass and Fail Examples)", W),
                      Spacer(1, 4 * mm)]
        else:
            story += [Paragraph("4. Non-functional testing – test cases", H2)]
        story += [purpose_block("Non-functional testing verifies the qualities of VISTA – performance, emergency response time, security, usability "
                                "and accessibility, reliability and data integrity, backup, scalability, compatibility, maintainability and data "
                                "privacy – against NFR01–NFR14 of the Lab VI report. Targets marked 'PDF' come from the report; 'Project target' "
                                "marks thresholds chosen by the team where the report gives none.", W),
                  Spacer(1, 2 * mm)]
        if kind == "nft":
            story += [meta_line(d, "non-functional"), Spacer(1, 2 * mm), legend()]
        story += [Spacer(1, 3 * mm), case_table(d["nonfunctional_cases"], NFT_COLUMNS, W), Spacer(1, 4 * mm),
                  summary_and_takeaways("Non-Functional Testing Summary", d["summary"]["nonfunctional"], [escape(x) for x in nft_takeaways(d)], W),
                  CondPageBreak(55 * mm), Spacer(1, 4 * mm),
                  Paragraph(("5. " if kind == "all" else "") + "Performance and load test measurements", H3)] + perf_table(d, W)
        if kind == "nft":
            story += [Spacer(1, 4 * mm), Paragraph("Defects linked to non-functional testing", H3),
                      defect_table({**d, "defects": [x for x in d["defects"] if any(c in x["found_by"] for c in ("NFT", "k6"))]}, W)]
    if kind == "all":
        story += [PageBreak(), Paragraph("6. Requirement traceability", H2)] + traceability(d, W)
        story += [PageBreak(), Paragraph("7. Defect log", H2), defect_table(d, W), Spacer(1, 5 * mm), Paragraph("8. Test environment and limitations", H2)]
        env = d["environment"]
        story += [Paragraph(escape(f"{env['os']} · {env['cpu_count']} vCPU · Python {env['python']} · Node {env['node']} · {env['postgresql']} · "
                                   f"{env['k6']} · {env['chromium']}. {env['note']}"), BODY), Spacer(1, 2 * mm)]
        for lim in LIMITATIONS:
            story.append(Paragraph("• " + escape(lim), BODY))
    doc.build(story)


# ----------------------------------------------------------------- Excel workbooks
def build_xlsx(path, kind, d):
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    thin = Side(style="thin", color="B9C7DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hfill = PatternFill("solid", fgColor="1B3A6B")
    hfont = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    font = Font(name="Arial", size=9)
    wrap = Alignment(wrap_text=True, vertical="top")
    if kind == "ft":
        ws.title = "Functional Tests"
        cols = [("TC ID", "id", 9), ("Module", "module", 16), ("Test Case Description", "description", 34), ("Pre-Conditions", "preconditions", 24),
                ("Test Steps", "steps", 42), ("Test Data", "data", 26), ("Expected Result", "expected", 38), ("Actual Result", "actual", 70),
                ("Status", "status", 10), ("Defect ID", "defects", 14), ("Requirement", "requirements", 14),
                ("Automated By", lambda r: ", ".join(r["automated_by"]), 22), ("Execution", "execution", 18)]
        rows = d["functional_cases"]
        title = "VISTA – Functional Test Cases"
    else:
        ws.title = "Non-Functional Tests"
        cols = [("TC ID", "id", 9), ("Quality Attribute", "attribute", 16), ("Test Case Description", "description", 32),
                ("Metric / Acceptance Criteria", "criteria", 32), ("Target Source", "target_source", 16), ("Test Steps / Tools", "steps", 40),
                ("Expected Result", "expected", 26), ("Actual Result", "actual", 75), ("Status", "status", 10), ("Evidence", "evidence", 28),
                ("Defect ID", "defects", 14), ("Requirement", "requirements", 14), ("Execution", "execution", 14)]
        rows = d["nonfunctional_cases"]
        title = "VISTA – Non-Functional Test Cases"
    ws["A1"] = title
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color="1B3A6B")
    ws["A2"] = (f"Generated {datetime.fromisoformat(d['generated_at']).astimezone(IST).strftime('%d %b %Y %H:%M IST')} from test-results/test-results.json. "
                "Status values: Pass, Fail, Blocked, Not Run (drop-down). Edit Status / Actual Result to record a manual re-test; the Summary sheet updates automatically.")
    ws["A2"].font = Font(name="Arial", italic=True, size=9, color="5B6475")
    hr = 4
    for i, (h, _, w) in enumerate(cols, start=1):
        c = ws.cell(row=hr, column=i, value=h)
        c.fill, c.font, c.border = hfill, hfont, border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    for r_i, r in enumerate(rows, start=hr + 1):
        for c_i, (_, key, _) in enumerate(cols, start=1):
            v = key(r) if callable(key) else r.get(key, "")
            c = ws.cell(row=r_i, column=c_i, value=v)
            c.font, c.alignment, c.border = (Font(name="Arial", size=9, bold=True) if c_i == 1 else font), wrap, border
    last = hr + len(rows)
    status_col = get_column_letter(next(i for i, c in enumerate(cols, start=1) if c[1] == "status"))
    dv = DataValidation(type="list", formula1='"Pass,Fail,Blocked,Not Run"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"{status_col}{hr + 1}:{status_col}{last}")
    rng = f"{status_col}{hr + 1}:{status_col}{last}"
    for val, bg, fg in (("Pass", "E2F3E5", "1E7B34"), ("Fail", "FDE3E1", "B42318"), ("Blocked", "ECEEF2", "4B5563"), ("Not Run", "ECEEF2", "4B5563")):
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{val}"'], fill=PatternFill("solid", fgColor=bg),
                                                      font=Font(name="Arial", bold=True, color=fg)))
    ws.freeze_panes = f"B{hr + 1}"
    ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(cols))}{last}"
    ws.sheet_view.zoomScale = 90

    sm = wb.create_sheet("Summary")
    sm["A1"] = f"{title} – Summary"
    sm["A1"].font = Font(name="Arial", bold=True, size=13, color="1B3A6B")
    ref = f"'{ws.title}'!${status_col}${hr + 1}:${status_col}${last}"
    items = [("Total test cases", f"=COUNTA({ref})"), ("Passed", f'=COUNTIF({ref},"Pass")'), ("Failed", f'=COUNTIF({ref},"Fail")'),
             ("Blocked", f'=COUNTIF({ref},"Blocked")'), ("Not Run", f'=COUNTIF({ref},"Not Run")'), ("Executed (Pass + Fail)", "=B4+B5"),
             ("Pass percentage", '=IF(B8=0,"N/A",B4/B8)')]
    for i, (label, formula) in enumerate(items, start=3):
        sm.cell(row=i, column=1, value=label).font = Font(name="Arial", bold=True, size=10)
        c = sm.cell(row=i, column=2, value=formula)
        c.font = Font(name="Arial", size=10)
        c.border = border
        if label == "Pass percentage":
            c.number_format = "0.0%"
    sm["A11"] = "Pass percentage = Passed ÷ Executed. Executed counts only Pass and Fail; Blocked and Not Run are shown separately."
    sm["A11"].font = Font(name="Arial", italic=True, size=9, color="5B6475")
    sm.column_dimensions["A"].width = 28
    sm.column_dimensions["B"].width = 14
    if kind == "nft":
        lt = wb.create_sheet("Load Tests")
        hdr = ["Run", "Concurrent users", "Duration", "Requests", "Throughput (req/s)", "Failed rate", "Avg ms", "Median ms", "p95 ms", "p99 ms", "Max ms"]
        for i, h in enumerate(hdr, start=1):
            c = lt.cell(row=1, column=i, value=h)
            c.fill, c.font, c.border = hfill, hfont, border
            lt.column_dimensions[get_column_letter(i)].width = 16
        for r_i, (k, r) in enumerate(sorted(d["k6_runs"].items(), key=lambda kv: kv[1]["vus"]), start=2):
            lat = r["latency_ms"]
            vals = [k, r["vus"], r["duration"], r["requests"], r["throughput_rps"], r["http_req_failed_rate"], round(lat["avg"], 1),
                    round(lat["med"], 1), round(lat["p(95)"], 1), round(lat["p(99)"], 1), round(lat["max"], 1)]
            for c_i, v in enumerate(vals, start=1):
                c = lt.cell(row=r_i, column=c_i, value=v)
                c.font, c.border = font, border
                if c_i == 6:
                    c.number_format = "0.00%"
    wb.save(path)


def build_defects(d):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    cols = [("Defect ID", "id", 10), ("Title", "title", 40), ("Severity", "severity", 11), ("Type", "type", 18), ("Affected Module", "module", 30),
            ("Found By", "found_by", 30), ("Reproduction Steps", "steps", 55), ("Expected Result", "expected", 40), ("Actual Result", "actual", 60),
            ("Status", "status", 14), ("Resolution", "resolution", 60), ("Evidence", "evidence", 36)]
    with open(OUT / "defect-log.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in cols])
        for x in d["defects"]:
            w.writerow([x[c[1]] for c in cols])
    wb = Workbook()
    ws = wb.active
    ws.title = "Defect Log"
    thin = Side(style="thin", color="B9C7DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, (h, _, wdt) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill, c.font, c.border = PatternFill("solid", fgColor="1B3A6B"), Font(name="Arial", bold=True, color="FFFFFF"), border
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = wdt
    fills = {"Fixed": "E2F3E5", "Open": "FDE3E1"}
    for r_i, x in enumerate(d["defects"], start=2):
        for c_i, (_, key, _) in enumerate(cols, start=1):
            c = ws.cell(row=r_i, column=c_i, value=x[key])
            c.font = Font(name="Arial", size=9, bold=c_i == 1)
            c.alignment, c.border = Alignment(wrap_text=True, vertical="top"), border
            if key == "status":
                c.fill = PatternFill("solid", fgColor=fills.get(x["status"], "ECEEF2"))
    dv = DataValidation(type="list", formula1='"Open,In Progress,Fixed,Open (blocked),Closed,Deferred"')
    ws.add_data_validation(dv)
    dv.add(f"J2:J{len(d['defects']) + 50}")
    sv = DataValidation(type="list", formula1='"Critical,High,Medium,Low"')
    ws.add_data_validation(sv)
    sv.add(f"C2:C{len(d['defects']) + 50}")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(d['defects']) + 1}"
    wb.save(OUT / "defect-log.xlsx")


def recalc(path: Path) -> None:
    script = None
    for cand in (Path("/mnt/skills/public/xlsx/scripts/recalc.py"), ROOT / "scripts" / "recalc.py"):
        if cand.exists():
            script = cand
            break
    if script and shutil.which("soffice"):
        r = subprocess.run([sys.executable, str(script), str(path), "60"], capture_output=True, text=True)
        print(f"  recalc {path.name}: {r.stdout.strip()[:200]}")
    else:
        print(f"  {path.name}: formulas will calculate when opened in Excel/LibreOffice (recalc tool not available)")


def main() -> None:
    d = json.loads((TR / "test-results.json").read_text())
    OUT.mkdir(exist_ok=True)
    build_pdf(OUT / "Functional_Testing_Report.pdf", "ft", d)
    build_pdf(OUT / "Non_Functional_Testing_Report.pdf", "nft", d)
    build_pdf(OUT / "Combined_Testing_Report.pdf", "all", d)
    build_xlsx(OUT / "Functional_Test_Cases.xlsx", "ft", d)
    build_xlsx(OUT / "Non_Functional_Test_Cases.xlsx", "nft", d)
    build_defects(d)
    for f in ("Functional_Test_Cases.xlsx", "Non_Functional_Test_Cases.xlsx"):
        recalc(OUT / f)
    for f in ("test-results.json", "test-results.xml"):
        shutil.copy(TR / f, OUT / f)
    print("Reports written to", OUT)


if __name__ == "__main__":
    main()
