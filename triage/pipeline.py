"""The whole intake: audio or text -> chart -> probabilities -> loss rule -> nurse sheet + JSON.

    speech-to-text (local Whisper)  ->  Gemini (dialect to JSON)  ->  Jev (five ESI probabilities)
    ->  Python asymmetric loss  ->  PDF + JSON

Every step reports where its output came from. Anything that is not live model output is labeled
(HACKATHON_TEST_DRIVE.md section 5.4), on screen, on the PDF, and in the JSON.
The official ESI is never assigned here: the PDF leaves that line blank for the RN.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import asr as asr_module
from . import fixtures
from .config import OUTPUT_DIR, get_settings
from .extraction import MODES, ExtractionOutcome, extract
from .jev import JevOutcome, score
from .loss import calculate_safest_esi
from .pdf_sheet import SheetData, build_sheet_pdf
from .schemas import TriageFlag
from .util import elapsed_ms, now

HOLD_LABEL = "OFFLINE SAFETY HOLD - SUGGESTED REVIEW ESI 2"
FIXTURE_PROBS_LABEL = "FIXTURE PROBABILITIES - NOT MODEL OUTPUT"
FIXTURE_CHART_LABEL = "FIXTURE CHART - NOT MODEL OUTPUT"
DISCLAIMER = "Administrative intake aid. Not a diagnosis. The RN assigns ESI."


class PipelineError(Exception):
    """The intake could not produce a sheet (for example: no transcript at all)."""


@dataclass
class PipelineResult:
    case_label: str
    fixture_id: Optional[str]
    mode: str
    arrival: str
    transcript: str
    transcript_source: str          # "whisper" | "typed" | "fixture_text"
    asr: Optional[asr_module.AsrOutcome]
    extraction: ExtractionOutcome
    scoring: JevOutcome
    flag: TriageFlag
    label_kind: str                 # "live" | "fixture" | "hold"
    headline_label: str
    step_lines: list[str]
    latency_ms: dict[str, float]
    notes: list[str] = field(default_factory=list)
    pdf_path: Optional[Path] = None
    json_path: Optional[Path] = None

    def to_dict(self) -> dict:
        return {
            "case": self.case_label,
            "fixture_id": self.fixture_id,
            "arrival": self.arrival,
            "mode": self.mode,
            "disclaimer": DISCLAIMER,
            "official_esi": None,   # always blank: the RN assigns it
            "labels": {"headline": self.headline_label, "kind": self.label_kind, "steps": self.step_lines},
            "transcript": {"text": self.transcript, "source": self.transcript_source},
            "speech_to_text": None if self.asr is None else {
                "model": self.asr.model, "seconds_of_audio": self.asr.audio_seconds,
                "language": self.asr.language, "language_probability": self.asr.language_probability,
            },
            "extraction": {
                "source": self.extraction.source, "model": self.extraction.model,
                "prompt_version": self.extraction.prompt_version, "note": self.extraction.note,
                "unverified_quotes": self.extraction.unverified_quotes,
                "chart": self.extraction.chart.model_dump(),
            },
            "scoring": {
                "source": self.scoring.source, "model": self.scoring.model,
                "prompt_version": self.scoring.prompt_version, "option_order": self.scoring.option_order,
                "choice": self.scoring.choice, "confidence": self.scoring.confidence,
                "probabilities": self.scoring.probabilities, "note": self.scoring.note,
            },
            "flag": self.flag.model_dump(),
            "notes": self.notes,
            "latency_ms": self.latency_ms,
        }


def _labels(
    asr_outcome: Optional[asr_module.AsrOutcome],
    transcript_source: str,
    extraction: ExtractionOutcome,
    scoring: JevOutcome,
) -> tuple[str, str, list[str]]:
    """Headline label, its kind, and one line per step. Worst source wins (hold > fixture > live)."""
    if transcript_source == "whisper" and asr_outcome is not None:
        stt = f"Speech-to-text: {asr_outcome.model} (live, {asr_outcome.latency_ms / 1000:.1f} s)"
        stt_short = asr_outcome.model
    elif transcript_source == "typed":
        stt, stt_short = "Speech-to-text: none (typed transcript)", "typed transcript"
    else:
        stt, stt_short = "Speech-to-text: none (stored fixture transcript)", "stored transcript"

    if extraction.source == "gemini":
        ext = f"Extraction: {extraction.model} (live, prompt {extraction.prompt_version})"
    elif extraction.source == "fixture_chart":
        ext = "Extraction: stored fixture chart (not model output)"
    else:
        ext = "Extraction: keyword scan (safety hold, no language model)"

    if scoring.source == "jev":
        sco = f"Scoring: {scoring.model} (live, prompt {scoring.prompt_version}, options {scoring.option_order})"
    elif scoring.source == "fixture_probs":
        sco = "Scoring: stored fixture probabilities (not model output)"
    else:
        sco = "Scoring: no probabilities (conservative ESI 2 safety hold)"

    if extraction.source == "regex_hold" or scoring.source == "regex_hold":
        return HOLD_LABEL, "hold", [stt, ext, sco]
    if scoring.source == "fixture_probs":
        return FIXTURE_PROBS_LABEL, "fixture", [stt, ext, sco]
    if extraction.source == "fixture_chart":
        return FIXTURE_CHART_LABEL, "fixture", [stt, ext, sco]
    return f"LIVE: {stt_short} + {extraction.model} + {scoring.model}", "live", [stt, ext, sco]


def run_pipeline(
    *,
    transcript: Optional[str] = None,
    audio_path: Optional[str | Path] = None,
    fixture_id: Optional[str] = None,
    mode: str = "auto",
    make_pdf: bool = True,
    out_dir: Optional[str | Path] = None,
    case_label: Optional[str] = None,
) -> PipelineResult:
    """Run one intake.

    Give audio_path, or transcript, or just fixture_id (uses the stored transcript).
    mode: "auto" (live where keys exist, stored fixtures otherwise), "offline" (never call an API),
          "outage" (simulate an API outage: conservative ESI 2 safety hold).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    settings = get_settings()
    total_start = now()
    latency: dict[str, float] = {}
    notes: list[str] = []
    fid = fixture_id
    asr_outcome: Optional[asr_module.AsrOutcome] = None

    # 1. transcript -------------------------------------------------------------------------
    if audio_path is not None:
        try:
            asr_outcome = asr_module.transcribe(audio_path)
            text, source = asr_outcome.text, "whisper"
            latency["asr"] = asr_outcome.latency_ms
            if asr_outcome.load_ms:
                latency["asr_model_load"] = asr_outcome.load_ms
            if not text.strip():
                raise PipelineError("Speech-to-text returned no words (silent or unreadable audio).")
        except PipelineError:
            raise
        except Exception as exc:
            if not fid:
                raise PipelineError(f"Speech-to-text failed ({type(exc).__name__}: {str(exc)[:160]}).") from exc
            text, source, asr_outcome = fixtures.load_transcript(fid), "fixture_text", None
            notes.append(f"Speech-to-text failed ({type(exc).__name__}); used the stored fixture transcript.")
    elif transcript is not None:
        text, source = transcript.strip(), "typed"
        fid = fid or fixtures.match_fixture(text)
    elif fid:
        text, source = fixtures.load_transcript(fid), "fixture_text"
    else:
        raise PipelineError("Give a transcript, an audio file, or a fixture id.")
    if not text.strip():
        raise PipelineError("The transcript is empty.")

    # 2. Gemini: Spanish -> chart ---------------------------------------------------------------
    extraction = extract(text, fixture_id=fid, mode=mode)
    latency["gemini"] = extraction.latency_ms
    if extraction.note:
        notes.append(extraction.note)

    # 3. Jev: chart -> five probabilities. Skipped when only the keyword hold exists. ---------
    scoring_mode = "outage" if extraction.source == "regex_hold" else mode
    scoring = score(extraction.chart, fixture_id=fid, mode=scoring_mode)
    latency["jev"] = scoring.latency_ms
    if scoring.note and extraction.source != "regex_hold":
        notes.append(scoring.note)

    # 4. Python: asymmetric loss -> suggested review tier --------------------------------------
    loss_start = now()
    if scoring.probabilities is not None:
        d = calculate_safest_esi(scoring.probabilities, settings.c_under, settings.c_over)
        flag = TriageFlag(
            probabilities=d["probabilities"],
            raw_argmax_tier=d["raw_argmax_tier"],
            suggested_review_tier=d["optimal_safety_tier"],
            expected_losses=d["expected_losses"],
            override_triggered=d["override_triggered"],
            jev_confidence=scoring.confidence,
            source="jev" if scoring.source == "jev" else "fixture",
        )
    else:
        flag = TriageFlag(suggested_review_tier=2, source="regex_hold")
    latency["loss"] = elapsed_ms(loss_start)

    # 5. labels, sheet, JSON --------------------------------------------------------------------------
    headline, kind, steps = _labels(asr_outcome, source, extraction, scoring)
    label = fixtures.title(fid) if fid else (case_label or ("Uploaded audio" if audio_path else "Custom transcript"))
    arrival = datetime.now().strftime("%Y-%m-%d %H:%M")
    result = PipelineResult(
        case_label=label, fixture_id=fid, mode=mode, arrival=arrival, transcript=text,
        transcript_source=source, asr=asr_outcome, extraction=extraction, scoring=scoring, flag=flag,
        label_kind=kind, headline_label=headline, step_lines=steps, latency_ms=latency, notes=notes,
    )

    if make_pdf:
        out = Path(out_dir) if out_dir else OUTPUT_DIR
        # milliseconds in the name: two runs of the same case inside one second must not overwrite each other
        stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]}_{fid or 'custom'}"
        pdf_start = now()
        # On the sheet, only mention problems (a live call that failed); the step lines already say what was stored.
        short_notes = [f"Note: {n[:100]}" for n in notes if "failed" in n][:2]
        build_sheet_pdf(
            SheetData(
                case_label=label, arrival=arrival, headline_label=headline, label_kind=kind,
                step_lines=steps + short_notes, chart=extraction.chart, flag=flag,
                unverified_quotes=extraction.unverified_quotes,
            ),
            out / f"{stem}.pdf",
        )
        latency["pdf"] = elapsed_ms(pdf_start)
        result.pdf_path = out / f"{stem}.pdf"
        latency["total"] = elapsed_ms(total_start)
        flag.latency_ms = dict(latency)
        result.json_path = out / f"{stem}.json"
        result.json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        latency["total"] = elapsed_ms(total_start)
        flag.latency_ms = dict(latency)
    return result
