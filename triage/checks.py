"""Checks on an extracted chart: are the quotes real, and does it match the gold values?

verify_quotes is part of the product: a quote that is not in the transcript is marked on the
nurse's sheet, because the read-back is the only check on Gemini (Jev does not verify it).
check_gold is for tests and for scoring live Gemini output against the fixtures.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from .fixtures import normalize_text
from .schemas import QUOTE_FIELDS, ExtractionResult

# A quote counts as "found" when every substantive word of it (4+ letters) appears in the transcript,
# in order, close together. A word matches if it is spelled almost the same ("pa'l" vs "pal",
# "sudo" vs "sudor") and digits count as their Spanish words ("9" = "nueve"), because Whisper writes
# numbers as digits. A word that is MISSING or replaced by different letters ("arde" heard as
# "enemear") is not tolerated: that is exactly the symptom word the nurse needs to know was lost.
WORD_SIMILARITY = 0.8
MIN_CONTENT_LETTERS = 4
DIGIT_WORDS = {
    "0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro", "5": "cinco", "6": "seis",
    "7": "siete", "8": "ocho", "9": "nueve", "10": "diez", "11": "once", "12": "doce",
}


def _quote_parts(quote: str) -> list[str]:
    return [p.strip() for p in quote.split(";") if p.strip()]


def _canon(words: list[str]) -> list[str]:
    return [DIGIT_WORDS.get(w, w) for w in words]


def _same_word(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= WORD_SIMILARITY


def _quote_found(quote: str, transcript_words: list[str]) -> bool:
    words = _canon(normalize_text(quote).split())
    content = [w for w in words if len(w) >= MIN_CONTENT_LETTERS]
    if not content:
        return True
    span = len(words) + 3
    for start in range(len(transcript_words)):
        window = transcript_words[start : start + span]
        pos = 0
        for word in content:
            hit = next((j for j in range(pos, len(window)) if _same_word(word, window[j])), None)
            if hit is None:
                break
            pos = hit + 1
        else:
            return True
    return False


def verify_quotes(chart: ExtractionResult, transcript: str) -> list[str]:
    """Field names whose quote is NOT found in the transcript (accents, punctuation, small spelling slips ignored)."""
    transcript_words = _canon(normalize_text(transcript).split())
    bad: list[str] = []
    for field in QUOTE_FIELDS:
        quote = getattr(chart.source_phrases, field)
        if not quote:
            continue
        if any(not _quote_found(part, transcript_words) for part in _quote_parts(quote)):
            bad.append(field)
    return bad


def fields_without_quote(chart: ExtractionResult) -> list[str]:
    """Fields that carry a real value but have no quote. (RP-G1 rule 5 says this must not happen.)"""
    filled = {
        "location": chart.location != "unknown",
        "onset": chart.onset != "unknown",
        "provocation": chart.provocation != "none stated",
        "quality": chart.quality != "unknown",
        "radiation": chart.radiation != ["none"],
        "severity_1_to_10": chart.severity_1_to_10 is not None,
        "timing_duration_hours": chart.timing_duration_hours is not None,
        "red_flag_symptoms": bool(chart.red_flag_symptoms),
    }
    return [f for f in QUOTE_FIELDS if filled[f] and not getattr(chart.source_phrases, f)]


def check_gold(chart: ExtractionResult, gold: dict) -> list[str]:
    """Compare a chart to the auto-check values in fixtures/gold.json. Returns failure messages."""
    failures: list[str] = []

    for field in ("location", "quality"):
        if field in gold and getattr(chart, field) != gold[field]:
            failures.append(f"{field}: expected {gold[field]!r}, got {getattr(chart, field)!r}")

    if "radiation_set" in gold and set(chart.radiation) != set(gold["radiation_set"]):
        failures.append(f"radiation: expected {sorted(gold['radiation_set'])}, got {sorted(chart.radiation)}")

    if "severity" in gold and chart.severity_1_to_10 != gold["severity"]:
        failures.append(f"severity_1_to_10: expected {gold['severity']}, got {chart.severity_1_to_10}")

    if "duration_hours" in gold:
        expected, tol = gold["duration_hours"]
        got = chart.timing_duration_hours
        if got is None or abs(got - expected) > tol:
            failures.append(f"timing_duration_hours: expected {expected} +/- {tol}, got {got}")

    flags = set(chart.red_flag_symptoms)
    if "red_flags_include" in gold:
        missing = set(gold["red_flags_include"]) - flags
        if missing:
            failures.append(f"red_flag_symptoms missing {sorted(missing)} (got {sorted(flags)})")
    if "red_flags_exact" in gold and flags != set(gold["red_flags_exact"]):
        failures.append(f"red_flag_symptoms: expected exactly {sorted(gold['red_flags_exact'])}, got {sorted(flags)}")

    if "forbidden_words" in gold:
        text = normalize_text(f"{chart.provocation} {chart.raw_summary_en}")
        leaked = [w for w in gold["forbidden_words"] if normalize_text(w) in text]
        if leaked:
            failures.append(f"social talk leaked into the chart: {leaked}")

    return failures
