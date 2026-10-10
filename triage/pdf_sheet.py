"""Step 5: the one-page nurse confirmation sheet (Contract 4, HACKATHON_TEST_DRIVE.md section 3).

This is a READ-BACK sheet, not a second interview: the nurse confirms or corrects each line with the patient.
It shows a SUGGESTED REVIEW TIER (a safety flag). The line "Official ESI assigned by RN" is always blank.
Everything is wrapped in a shrink-to-fit frame, so it can never spill onto a second page.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepInFrame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import ExtractionResult, TriageFlag

PAGE_W, PAGE_H = letter
MARGIN = 36
FRAME_W = PAGE_W - 2 * MARGIN   # 540
FRAME_H = PAGE_H - 2 * MARGIN   # 720

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
GRID = colors.HexColor("#cbd5e1")
PANEL = colors.HexColor("#f1f5f9")
LABEL_COLORS = {                      # background, text
    "live": (colors.HexColor("#e0f2fe"), colors.HexColor("#075985")),
    "fixture": (colors.HexColor("#fef3c7"), colors.HexColor("#92400e")),
    "hold": (colors.HexColor("#fee2e2"), colors.HexColor("#b91c1c")),
}
URGENT_BG = colors.HexColor("#fee2e2")
URGENT_FG = colors.HexColor("#b91c1c")

DISCLAIMER = (
    "Administrative intake aid. Not a diagnosis. The suggested review tier is a safety flag computed from "
    "model probabilities. The RN assigns ESI."
)


@dataclass
class SheetData:
    """Everything the sheet needs. The pipeline fills this; tests can build it by hand."""

    case_label: str
    arrival: str
    headline_label: str                 # one of the labels in section 5.4
    label_kind: str                     # "live" | "fixture" | "hold"
    step_lines: list[str]
    chart: ExtractionResult
    flag: TriageFlag
    unverified_quotes: list[str] = field(default_factory=list)
    # Filled only after the nurse confirms in the nurse screen: {"official_esi", "fields", "readback_seconds", "confirmed_at"}.
    # The official ESI then shown is the one the NURSE entered; the system never fills it in.
    confirmation: Optional[dict] = None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    def style(name, **kw):
        return ParagraphStyle(name, parent=base, fontName=kw.pop("fontName", "Helvetica"), **kw)
    return {
        "title": style("title", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK),
        "subtitle": style("subtitle", fontSize=9, leading=11, textColor=MUTED),
        "h": style("h", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=INK),
        "cell": style("cell", fontSize=9.2, leading=11.5, textColor=INK),
        "cellb": style("cellb", fontName="Helvetica-Bold", fontSize=9.2, leading=11.5, textColor=INK),
        "quote": style("quote", fontName="Helvetica-Oblique", fontSize=9.2, leading=11.5, textColor=INK),
        "small": style("small", fontSize=7.8, leading=9.5, textColor=MUTED),
        "label": style("label", fontName="Helvetica-Bold", fontSize=10.5, leading=13),
        "step": style("step", fontSize=7.8, leading=9.5),
        "big": style("big", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK),
        "foot": style("foot", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=MUTED),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """Paragraph from plain text (escaped, so patient or model text can never break the layout)."""
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _pretty(value: str) -> str:
    return value.replace("_", " ")


def _hours(hours) -> str:
    return "not stated" if hours is None else f"{hours:g} hours"


def _chart_rows(chart: ExtractionResult, unverified: list[str]) -> list[tuple[str, str, str | None, str]]:
    """(field label, extracted text, quote, source_phrases field name)"""
    sp = chart.source_phrases
    return [
        ("Location", _pretty(chart.location), sp.location, "location"),
        ("Onset", _pretty(chart.onset), sp.onset, "onset"),
        ("Provocation", chart.provocation, sp.provocation, "provocation"),
        ("Quality", _pretty(chart.quality), sp.quality, "quality"),
        ("Radiation", ", ".join(_pretty(r) for r in chart.radiation), sp.radiation, "radiation"),
        ("Severity", "not stated" if chart.severity_1_to_10 is None else f"{chart.severity_1_to_10}/10",
         sp.severity_1_to_10, "severity_1_to_10"),
        ("Duration", _hours(chart.timing_duration_hours), sp.timing_duration_hours, "timing_duration_hours"),
        ("Red flags", ", ".join(_pretty(r) for r in chart.red_flag_symptoms) or "none",
         sp.red_flag_symptoms, "red_flag_symptoms"),
    ]


def build_sheet_pdf(data: SheetData, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = _styles()
    flag = data.flag
    content: list = []

    # --- title ---------------------------------------------------------------
    conf = data.confirmation
    subtitle = ("CONFIRMED BY RN. Lines marked OK or corrected by the nurse after read-back." if conf else
                "Nurse confirmation sheet. Read back with the patient; confirm or correct each line.")
    content += [
        Paragraph("EMERGENCY DEPARTMENT AMBIENT INTAKE", s["title"]),
        Paragraph(subtitle, s["subtitle"]),
        Spacer(1, 6),
    ]

    # --- source label banner (never show a fixture as live) -----------------
    bg, fg = LABEL_COLORS.get(data.label_kind, LABEL_COLORS["hold"])
    label_style = ParagraphStyle("lab", parent=s["label"], textColor=fg)
    step_style = ParagraphStyle("stp", parent=s["step"], textColor=fg)
    banner = Table(
        [[_p(data.headline_label, label_style)], [_p(" | ".join(data.step_lines), step_style)]],
        colWidths=[FRAME_W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, fg),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    content += [banner, Spacer(1, 6)]

    # --- case info ---------------------------------------------------------------
    info = Table(
        [
            [_p(f"Patient arrival: {data.arrival}", s["cellb"]), _p("Primary language: Spanish (auto-parsed)", s["cellb"])],
            [_p(f"Case: {data.case_label}", s["cell"]), _p("Data: SYNTHETIC demonstration data, not a real patient", s["cell"])],
        ],
        colWidths=[FRAME_W / 2, FRAME_W / 2],
    )
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    content += [info, Spacer(1, 6)]

    # --- tier banner ------------------------------------------------------------------
    sug = flag.suggested_review_tier
    urgent = sug <= 2
    tier_fg = URGENT_FG if urgent else INK
    big = ParagraphStyle("bigtier", parent=s["big"], textColor=tier_fg)
    if flag.raw_argmax_tier is None:
        left = "Most likely tier: not available"
        sub = "No probabilities. Conservative safety hold: suggested review tier ESI 2."
    else:
        left = f"Model's most likely tier: ESI {flag.raw_argmax_tier}"
        if flag.override_triggered:
            sub = f"Safety rule raised the tier from ESI {flag.raw_argmax_tier} to ESI {sug} (under-triage costs 10x)."
        else:
            sub = "Safety rule agrees with the most likely tier."
        if flag.jev_confidence is not None:
            sub += f" Jev confidence: {flag.jev_confidence:.2f}."
    tier = Table(
        [[_p(left, s["cellb"]), Paragraph(f"SUGGESTED REVIEW TIER: ESI {sug}", big)], [_p("", s["cell"]), _p(sub, s["cell"])]],
        colWidths=[FRAME_W * 0.42, FRAME_W * 0.58],
    )
    tier.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), URGENT_BG if urgent else PANEL),
        ("BOX", (0, 0), (-1, -1), 1, tier_fg),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    content += [tier, Spacer(1, 8)]

    # --- read-back table ----------------------------------------------------------------
    content += [Paragraph("READ BACK WITH THE PATIENT", s["h"]), Spacer(1, 3)]
    rows = [[_p("Field", s["cellb"]), _p("Extracted", s["cellb"]), _p("Patient's own words (Spanish)", s["cellb"]), _p("RN confirm", s["cellb"])]]
    for label, value, quote, key in _chart_rows(data.chart, data.unverified_quotes):
        if quote:
            quote_cell = Paragraph(
                f"&quot;{escape(quote)}&quot;"
                + (' <font color="#b91c1c">(not found in transcript)</font>' if key in data.unverified_quotes else ""),
                s["quote"],
            )
        else:
            quote_cell = _p("-", s["cell"])
        decided = (conf or {}).get("fields", {}).get(key) if conf else None
        if decided and decided.get("status") == "corrected":
            confirm = Paragraph(f'<font color="#b91c1c"><b>Corrected by RN:</b> {escape(decided.get("value", ""))}</font>', s["cell"])
        elif conf:
            confirm = Paragraph("<b>[x] OK</b> (RN)", s["cell"])
        else:
            confirm = Paragraph("[ ] OK&nbsp;&nbsp;&nbsp;&nbsp;[ ] Correct to: ________", s["cell"])
        rows.append([_p(label, s["cellb"]), _p(value, s["cell"]), quote_cell, confirm])
    readback = Table(rows, colWidths=[74, 116, 204, 146], repeatRows=1)
    readback.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (0, -1), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    content += [readback, Spacer(1, 8)]

    # --- safety calculation ----------------------------------------------------------------
    content += [Paragraph("SAFETY CALCULATION (asymmetric loss: under-triage 10x, over-triage 1x)", s["h"]), Spacer(1, 3)]
    if flag.probabilities is not None and flag.expected_losses is not None:
        head = [_p("", s["cellb"])] + [_p(f"ESI {i}", s["cellb"]) for i in range(1, 6)]
        prob_row = [_p("Probability", s["cellb"])] + [_p(f"{p * 100:.0f}%", s["cell"]) for p in flag.probabilities]
        loss_row = [_p("Expected loss", s["cellb"])] + [_p(f"{x:.2f}", s["cell"]) for x in flag.expected_losses]
        calc = Table([head, prob_row, loss_row], colWidths=[100] + [88] * 5)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, GRID),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 1), (0, -1), PANEL),
            ("BACKGROUND", (sug, 0), (sug, -1), URGENT_BG if urgent else colors.HexColor("#dbeafe")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        calc.setStyle(TableStyle(style))
        content += [calc, Spacer(1, 3), Paragraph(
            "Expected loss of a tier = sum over the true tiers of P(true tier) x cost(tier, true tier). "
            "The suggested review tier is the column with the lowest expected loss (shaded). Lower is safer.", s["small"])]
    else:
        content += [Paragraph(
            "No probabilities are available for this case (offline safety hold). The conservative default "
            "suggested review tier is ESI 2. The nurse takes the history directly.", s["cell"])]
    content += [Spacer(1, 8)]

    # --- summary ---------------------------------------------------------------------------------
    content += [
        Paragraph("SUMMARY (restated from the patient's words; no diagnosis)", s["h"]), Spacer(1, 3),
        _p(data.chart.raw_summary_en or "-", s["cell"]), Spacer(1, 8),
    ]

    # --- RN verification and ESI (always blank) ----------------------------------------------
    content += [Paragraph("RN VERIFICATION AND ESI ASSIGNMENT", s["h"]), Spacer(1, 3)]
    sign = Table(
        [
            [_p("RN verification", s["cellb"]), _p("RN sign-off", s["cellb"])],
            [
                _p("[ ] Vitals taken\n[ ] Read-back confirmed with patient\n[ ] Interpreter used if needed", s["cell"]),
                _p("RN signature: ____________________________\n\nBadge ID: ______________   Time: __________", s["cell"]),
            ],
        ],
        colWidths=[FRAME_W / 2, FRAME_W / 2],
    )
    sign.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, MUTED),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    if conf:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(conf.get("confirmed_at") or time.time()))
        rb = conf.get("readback_seconds")
        esi_text = (f"OFFICIAL ESI ASSIGNED BY RN:&nbsp;&nbsp;ESI {int(conf['official_esi'])}"
                    f'<font size="9">&nbsp;&nbsp;&nbsp;(entered by the nurse {when}'
                    + (f"; read-back {rb:g} s" if rb is not None else "") + ")</font>")
    else:
        esi_text = "OFFICIAL ESI ASSIGNED BY RN:&nbsp;&nbsp;______________"
    esi = Table([[Paragraph(esi_text, s["big"])]], colWidths=[FRAME_W], rowHeights=[34])
    esi.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    content += [sign, Spacer(1, 6), esi, Spacer(1, 6), Paragraph(DISCLAIMER, s["foot"])]

    # --- build: one frame, shrink to fit so the sheet is always exactly one page -----------
    doc = BaseDocTemplate(
        str(path), pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title="ED ambient intake - nurse confirmation sheet", author="Ambient ER triage test drive",
    )
    frame = Frame(MARGIN, MARGIN, FRAME_W, FRAME_H, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    doc.addPageTemplates([PageTemplate(id="one", frames=[frame])])
    doc.build([KeepInFrame(FRAME_W, FRAME_H, content, mode="shrink")])
    return path


def render_preview(pdf_path: str | Path, scale: float = 1.6):
    """First page as a PIL image (for the Streamlit preview and for visual checks)."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf_path))
    try:
        return document[0].render(scale=scale).to_pil()
    finally:
        document.close()
