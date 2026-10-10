"""The nurse sheet: one page, honest labels, Spanish quotes, and an always-blank official ESI line."""

import re

import pypdf
import pytest

from triage import fixtures as fx
from triage.loss import calculate_safest_esi
from triage.pdf_sheet import SheetData, build_sheet_pdf, render_preview
from triage.schemas import ExtractionResult, TriageFlag


def make_flag(probs, confidence=None):
    d = calculate_safest_esi(probs)
    return TriageFlag(
        probabilities=d["probabilities"], raw_argmax_tier=d["raw_argmax_tier"],
        suggested_review_tier=d["optimal_safety_tier"], expected_losses=d["expected_losses"],
        override_triggered=d["override_triggered"], jev_confidence=confidence, source="fixture",
    )


def make_data(fid="A", label="FIXTURE PROBABILITIES - NOT MODEL OUTPUT", kind="fixture", flag=None, chart=None, unverified=()):
    return SheetData(
        case_label=fx.title(fid), arrival="2026-10-06 15:01", headline_label=label, label_kind=kind,
        step_lines=["Speech-to-text: typed transcript", "Extraction: stored fixture chart", "Scoring: stored fixture probabilities"],
        chart=chart or fx.load_chart(fid), flag=flag or make_flag(fx.load_probabilities(fid)),
        unverified_quotes=list(unverified),
    )


def read_pdf(path):
    reader = pypdf.PdfReader(str(path))
    text = "\n".join(page.extract_text() for page in reader.pages)
    return len(reader.pages), re.sub(r"\s+", " ", text)  # phrases wrap across lines on the page


def test_chest_pain_sheet_is_one_page_with_the_key_content(tmp_path):
    pdf = build_sheet_pdf(make_data("A"), tmp_path / "a.pdf")
    pages, text = read_pdf(pdf)
    assert pages == 1
    assert "SUGGESTED REVIEW TIER: ESI 2" in text
    assert "most likely tier: ESI 3" in text
    assert "Safety rule raised the tier from ESI 3 to ESI 2" in text
    assert "FIXTURE PROBABILITIES - NOT MODEL OUTPUT" in text
    assert "SYNTHETIC" in text
    assert "apretón en el pecho" in text            # the patient's own Spanish, accents intact
    assert "mandíbula" in text
    for needle in ("2%", "18%", "60%", "1.25", "10.25"):  # the audit trail is on the page
        assert needle in text


def test_ankle_sheet_says_the_rule_agrees(tmp_path):
    pages, text = read_pdf(build_sheet_pdf(make_data("B"), tmp_path / "b.pdf"))
    assert pages == 1
    assert "SUGGESTED REVIEW TIER: ESI 4" in text
    assert "Safety rule agrees" in text


def test_official_esi_line_is_always_blank(tmp_path):
    for fid in fx.FIXTURE_IDS:
        _, text = read_pdf(build_sheet_pdf(make_data(fid), tmp_path / f"{fid}.pdf"))
        match = re.search(r"OFFICIAL ESI ASSIGNED BY RN:\s*(_+)", text)
        assert match, "the blank official ESI line is missing"
        assert "Assigned Safety Tier" not in text


def test_safety_hold_sheet_has_no_probabilities_and_the_hold_label(tmp_path):
    flag = TriageFlag(suggested_review_tier=2, source="regex_hold")
    data = make_data("A", label="OFFLINE SAFETY HOLD - SUGGESTED REVIEW ESI 2", kind="hold", flag=flag)
    pages, text = read_pdf(build_sheet_pdf(data, tmp_path / "hold.pdf"))
    assert pages == 1
    assert "OFFLINE SAFETY HOLD - SUGGESTED REVIEW ESI 2" in text
    assert "SUGGESTED REVIEW TIER: ESI 2" in text
    assert "No probabilities are available" in text
    assert "Probability" not in text


def test_live_label_and_confidence_are_shown(tmp_path):
    data = make_data("C", label="LIVE: whisper small + gemini-3.8-flash + jev-1.13.0", kind="live",
                     flag=make_flag(fx.load_probabilities("C"), confidence=0.71))
    _, text = read_pdf(build_sheet_pdf(data, tmp_path / "live.pdf"))
    assert "LIVE: whisper small + gemini-3.8-flash + jev-1.13.0" in text
    assert "Jev confidence: 0.71" in text


def test_unverified_quote_is_marked_for_the_nurse(tmp_path):
    _, text = read_pdf(build_sheet_pdf(make_data("A", unverified=["quality"]), tmp_path / "u.pdf"))
    assert "not found in transcript" in text


def test_very_long_text_still_fits_on_one_page(tmp_path):
    chart = fx.load_chart("A")
    chart.provocation = "x " * 400
    chart.raw_summary_en = "The patient talked and talked. " * 60
    chart.source_phrases.onset = "palabra " * 120
    pages, _ = read_pdf(build_sheet_pdf(make_data("A", chart=chart), tmp_path / "long.pdf"))
    assert pages == 1


def test_markup_in_patient_text_cannot_break_the_layout(tmp_path):
    chart = fx.load_chart("A")
    chart.provocation = "<b>bold & <i>italic</b> </para>"
    chart.source_phrases.quality = "dice <script> & 'más'"
    pages, text = read_pdf(build_sheet_pdf(make_data("A", chart=chart), tmp_path / "markup.pdf"))
    assert pages == 1
    assert "<b>bold" in text                          # shown literally, not interpreted


def test_sparse_chart_renders_without_crashing(tmp_path):
    chart = ExtractionResult()                        # everything unknown
    pages, text = read_pdf(build_sheet_pdf(make_data("A", chart=chart), tmp_path / "sparse.pdf"))
    assert pages == 1
    assert "not stated" in text


def test_preview_renders_an_image(tmp_path):
    pdf = build_sheet_pdf(make_data("A"), tmp_path / "p.pdf")
    image = render_preview(pdf, scale=1.0)
    assert image.size[0] > 400 and image.size[1] > 500
