"""Loader for the synthetic fixtures (HACKATHON_TEST_DRIVE.md section 6)."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

from .config import FIXTURES_DIR
from .schemas import ExtractionResult

FIXTURE_IDS = ["A", "A_long", "B", "C"]

TITLES = {
    "A": "Case A - Chest pressure, left arm (demo clip)",
    "A_long": "Case A (long) - Chest pressure, rambling version",
    "B": "Case B - Ankle sprain",
    "C": "Case C - Ambiguous epigastric burning (spare)",
}


def _check(fixture_id: str) -> str:
    if fixture_id not in FIXTURE_IDS:
        raise KeyError(f"Unknown fixture {fixture_id!r}. Choose one of {FIXTURE_IDS}.")
    return fixture_id


def title(fixture_id: str) -> str:
    return TITLES[_check(fixture_id)]


def load_transcript(fixture_id: str) -> str:
    return (FIXTURES_DIR / "transcripts" / f"{_check(fixture_id)}.txt").read_text(encoding="utf-8").strip()


def load_chart(fixture_id: str) -> ExtractionResult:
    path = FIXTURES_DIR / "charts" / f"{_check(fixture_id)}.json"
    return ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))


def load_gold(fixture_id: str) -> dict:
    data = json.loads((FIXTURES_DIR / "gold.json").read_text(encoding="utf-8"))
    return data[_check(fixture_id)]


def load_probabilities(fixture_id: str) -> list[float]:
    data = json.loads((FIXTURES_DIR / "probabilities.json").read_text(encoding="utf-8"))
    return [float(x) for x in data[_check(fixture_id)]]


def audio_path(fixture_id: str) -> Optional[Path]:
    """Synthetic test clip if it exists. The real demo clip should be a human voice."""
    for name in (f"{_check(fixture_id)}.wav", f"{fixture_id}_synthetic.wav"):
        path = FIXTURES_DIR / "audio" / name
        if path.exists():
            return path
    return None


def normalize_text(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace. For matching only.

    Apostrophes are removed (not turned into spaces) so "pa'l" and "pal" compare equal.
    """
    text = text.lower().replace("'", "").replace("\u2019", "")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_fixture(transcript: str) -> Optional[str]:
    """Return the fixture id whose transcript equals this text (ignoring accents/punctuation)."""
    target = normalize_text(transcript)
    for fixture_id in FIXTURE_IDS:
        if normalize_text(load_transcript(fixture_id)) == target:
            return fixture_id
    return None
