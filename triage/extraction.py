"""Step 2: Spanish transcript -> validated OPQRST chart (Contract 1).

Three possible sources, always labeled downstream:
  gemini         live call to Gemini (needs GOOGLE_API_KEY)
  fixture_chart  stored chart for a known fixture (no key, offline mode, or the live call failed)
  regex_hold     deterministic keyword scan -> conservative ESI 2 safety hold (spec section 5.3)

Gemini only normalizes language into fixed fields. It never assigns an ESI tier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from pydantic import ValidationError

from . import fixtures
from .checks import verify_quotes
from .config import Settings, get_settings
from .prompts import GEMINI_PROMPT_VERSION, GEMINI_SYSTEM_PROMPT
from .schemas import ExtractionResult, SourcePhrases
from .util import ApiTimeout, call_with_timeout, elapsed_ms, mask_secrets, now

MODES = ("auto", "offline", "outage")


class ExtractionError(Exception):
    """Gemini answered, but not with a usable chart."""


@dataclass
class ExtractionOutcome:
    chart: ExtractionResult
    source: str  # "gemini" | "fixture_chart" | "regex_hold"
    latency_ms: float
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    note: Optional[str] = None
    unverified_quotes: list[str] = field(default_factory=list)
    raw_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Regex safety hold (offline / outage fallback)
# ---------------------------------------------------------------------------

RED_FLAG_PATTERNS = {
    "chest_pain": r"\bpecho\b",
    "dyspnea": r"falta (de |el )?aire|falta la respiracion|me ahogo|\bahogo\b|sofoc|no puedo respirar|no puedo coger aire|respiro mal|dificultad (para|al) respirar|me cuesta respirar|short of breath",
    "syncope": r"desmay|patatus|me prive|perdi el conocimiento|se me fue la luz|me desvanec",
    "uncontrolled_bleeding": r"sangr|hemorragia",
    "stroke_signs": r"cara torcida|no puedo hablar|habla arrastrada|no siento (el |la )?(brazo|pierna|cara)|debilidad (en )?(un lado|el brazo|la pierna)",
    "diaphoresis": r"sudor frio|sudando frio|sudo frio|sudor helado",
}
RADIATION_PATTERNS = {
    "left_arm": r"brazo izquierdo",
    "jaw": r"mandibula",
    "neck": r"\bcuello\b",
    "back": r"espalda",
    "abdomen": r"\babdomen\b|barriga",
}


def regex_hold_chart(transcript: str) -> ExtractionResult:
    """Keyword scan of the transcript. Quotes are the whole sentence that contained the keyword."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", transcript) if s.strip()]
    flags: list[str] = []
    flag_quotes: list[str] = []
    radiation: list[str] = []
    radiation_quotes: list[str] = []

    for sentence in sentences:
        norm = fixtures.normalize_text(sentence)
        for flag, pattern in RED_FLAG_PATTERNS.items():
            if re.search(pattern, norm):
                if flag not in flags:
                    flags.append(flag)
                if sentence not in flag_quotes:
                    flag_quotes.append(sentence)
        for rad, pattern in RADIATION_PATTERNS.items():
            if re.search(pattern, norm):
                if rad not in radiation:
                    radiation.append(rad)
                if sentence not in radiation_quotes:
                    radiation_quotes.append(sentence)

    found = ", ".join(flags) if flags else "none"
    return ExtractionResult(
        location="chest" if "chest_pain" in flags else "unknown",
        radiation=radiation or ["none"],
        red_flag_symptoms=flags,
        source_phrases=SourcePhrases(
            red_flag_symptoms="; ".join(flag_quotes) or None,
            radiation="; ".join(radiation_quotes) or None,
        ),
        raw_summary_en=(
            "Offline safety hold. The language model was not used, so only keyword scanning was done. "
            f"Keywords found: {found}."
        ),
    )


# ---------------------------------------------------------------------------
# Live Gemini call
# ---------------------------------------------------------------------------

def _gemini_call(transcript: str, settings: Settings, extra: str = "") -> str:
    """One call to Gemini. Returns the raw text. Kept separate so tests can replace it."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.google_api_key,
        http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_s * 1000)),
    )
    config_kwargs = {
        "system_instruction": GEMINI_SYSTEM_PROMPT,
        "response_mime_type": "application/json",
    }
    if settings.gemini_thinking_level:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=settings.gemini_thinking_level)
    contents = transcript if not extra else f"{transcript}\n\n{extra}"
    models_to_try = [settings.gemini_model]
    if settings.gemini_model != "gemini-2.5-flash":
        models_to_try.append("gemini-2.5-flash")

    last_exc = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = response.text
            if text and text.strip():
                return text
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise ExtractionError("Gemini returned an empty response")


def parse_json_text(text: str) -> dict:
    """Parse model output as JSON, tolerating markdown fences or a sentence around the object."""
    cleaned = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data


def extract_live(transcript: str, settings: Optional[Settings] = None) -> tuple[ExtractionResult, str]:
    """Call Gemini, validate, retry once on invalid output. Raises on failure."""
    settings = settings or get_settings()
    extra = ""
    last_error: Exception | None = None
    for _attempt in (1, 2):
        # outer guard slightly above the SDK's own HTTP timeout
        text = call_with_timeout(_gemini_call, settings.gemini_timeout_s + 1.0, transcript, settings, extra)
        try:
            chart = ExtractionResult.model_validate(parse_json_text(text))
            return chart, text
        except (ValueError, ValidationError) as exc:
            last_error = exc
            extra = (
                "Your previous reply could not be used: "
                f"{str(exc)[:300]}. Reply again with the JSON object only, following the schema exactly."
            )
    raise ExtractionError(f"Gemini output failed validation twice: {str(last_error)[:300]}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract(
    transcript: str,
    *,
    fixture_id: Optional[str] = None,
    mode: str = "auto",
) -> ExtractionOutcome:
    """Produce a chart for this transcript.

    mode "auto":    live Gemini if a key is set, otherwise (or if the call fails) the stored fixture
                    chart when the transcript is a known fixture, otherwise the regex hold.
    mode "offline": never call an API. Fixture chart if known, otherwise the regex hold.
    mode "outage":  simulate an API outage. Always the regex hold.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    settings = get_settings()
    fid = fixture_id or fixtures.match_fixture(transcript)
    start = now()

    def finish(chart, source, *, model=None, prompt_version=None, note=None, raw=None):
        return ExtractionOutcome(
            chart=chart,
            source=source,
            latency_ms=elapsed_ms(start),
            model=model,
            prompt_version=prompt_version,
            note=note,
            unverified_quotes=verify_quotes(chart, transcript),
            raw_text=raw,
        )

    if mode == "outage":
        return finish(regex_hold_chart(transcript), "regex_hold", note="Simulated API outage.")

    note: Optional[str] = None
    if mode == "auto" and settings.gemini_live_ready:
        try:
            chart, raw = extract_live(transcript, settings)
            return finish(
                chart, "gemini", model=settings.gemini_model, prompt_version=GEMINI_PROMPT_VERSION, raw=raw
            )
        except (ApiTimeout, ExtractionError) as exc:
            note = f"Gemini call failed: {mask_secrets(str(exc), settings.google_api_key)[:200]}"
        except Exception as exc:  # SDK, network, auth errors: never crash the intake flow
            note = (
                f"Gemini call failed ({type(exc).__name__}): "
                f"{mask_secrets(str(exc), settings.google_api_key)[:200]}"
            )
    elif mode == "offline" or settings.force_offline:
        note = "Offline mode: no API call was made."
    else:
        note = "No GOOGLE_API_KEY set: no API call was made."

    if fid:
        return finish(fixtures.load_chart(fid), "fixture_chart", note=note)
    return finish(regex_hold_chart(transcript), "regex_hold", note=note)
