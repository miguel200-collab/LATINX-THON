"""Step 3: structured chart -> five ESI probabilities + confidence, from Jev (TypeSafe System One).

Jev reads ONLY the structured fields (Contract 2). It does not see the transcript, the Spanish
quotes, or the English summary. It does not verify Gemini and it does not assign the official ESI:
Python applies the asymmetric loss to these probabilities and prints a suggested review tier.

Sources, always labeled downstream:
  jev             live call (needs TYPESAFE_API_KEY)
  fixture_probs   stored worked-example vector for a known fixture (no key, offline, or live call failed)
  regex_hold      no probabilities available: conservative ESI 2 safety hold
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from . import fixtures
from .config import Settings, get_settings
from .prompts import (
    ESI_KEYS,
    JEV_CRITERIA,
    JEV_INSTRUCTIONS,
    JEV_PROMPT_VERSION,
    JEV_QUESTION_ID,
)
from .schemas import ExtractionResult
from .util import ApiTimeout, call_with_timeout, elapsed_ms, mask_secrets, now

ORDERS = ("forward", "reversed")


class JevError(Exception):
    """Jev answered, but not with a usable ESI distribution."""


@dataclass
class JevOutcome:
    probabilities: Optional[list[float]]  # P(ESI 1..5), or None for the safety hold
    confidence: Optional[float]
    choice: Optional[str]
    source: str  # "jev" | "fixture_probs" | "regex_hold"
    latency_ms: float
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    option_order: str = "forward"
    note: Optional[str] = None


def _ordered_keys(order: str) -> list[str]:
    if order not in ORDERS:
        raise ValueError(f"order must be one of {ORDERS}")
    return list(ESI_KEYS) if order == "forward" else list(reversed(ESI_KEYS))


def build_question(order: str = "forward"):
    """The Choice question. Reversed order is for the option-order bias check."""
    from typesafe_sdk import Choice

    return Choice(
        instructions=JEV_INSTRUCTIONS,
        criteria={key: JEV_CRITERIA[key] for key in _ordered_keys(order)},
    )


def probability_vector(probabilities: dict[str, float]) -> list[float]:
    """Build [p1..p5] by KEY, never by position (the API does not promise an order)."""
    missing = [k for k in ESI_KEYS if k not in probabilities]
    if missing:
        raise JevError(f"Jev response is missing options {missing}")
    vector = [float(probabilities[k]) for k in ESI_KEYS]
    if any(p < 0 for p in vector) or sum(vector) <= 0:
        raise JevError(f"Jev returned unusable probabilities {vector}")
    return vector


def _jev_call(state: dict, settings: Settings, order: str = "forward") -> dict:
    """One call to Jev. Returns plain data. Kept separate so tests can replace it."""
    from typesafe_sdk import TypeSafeClient

    question = build_question(order)
    with TypeSafeClient(
        api_key=settings.typesafe_api_key,
        model=settings.jev_model,
        timeout=settings.jev_timeout_s,
    ) as client:
        response = client.system_one(state=state, questions={JEV_QUESTION_ID: question})
    answer = response.choices[JEV_QUESTION_ID]
    return {
        "choice": answer.choice,
        "confidence": answer.confidence,
        "probabilities": dict(answer.probabilities),
        "model": response.model,
    }


def score_live(chart: ExtractionResult, settings: Optional[Settings] = None, order: str = "forward") -> JevOutcome:
    """Live Jev call. Raises on any failure (no fallback). Used by score() and the sanity checks."""
    settings = settings or get_settings()
    if not settings.jev_live_ready:
        raise JevError("TYPESAFE_API_KEY is not set (or offline mode is on)")
    start = now()
    raw = call_with_timeout(_jev_call, settings.jev_timeout_s + 1.0, chart.jev_state(), settings, order)
    vector = probability_vector(raw["probabilities"])
    return JevOutcome(
        probabilities=vector,
        confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
        choice=raw.get("choice"),
        source="jev",
        latency_ms=elapsed_ms(start),
        model=raw.get("model"),
        prompt_version=JEV_PROMPT_VERSION,
        option_order=order,
    )


def _gemini_acuity_call(state: dict, settings: Settings, order: str = "forward") -> dict:
    """One call to Gemini evaluating acuity. Returns plain data."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.google_api_key)
    ordered_keys = _ordered_keys(order)
    criteria_text = "\n".join(f"- {k}: {JEV_CRITERIA[k]}" for k in ordered_keys)
    prompt = (
        f"You are an emergency severity assessment engine.\n"
        f"{JEV_INSTRUCTIONS}\n\n"
        f"Criteria:\n{criteria_text}\n\n"
        f"Patient Structured Symptoms:\n{json.dumps(state, indent=2)}\n\n"
        f"Assign a probability distribution over the five ESI levels (esi_1, esi_2, esi_3, esi_4, esi_5).\n"
        f"The probabilities must be non-negative numbers that sum to 1.0.\n"
        f"Also pick the single best choice (one of esi_1 .. esi_5) and give your confidence (0.0 to 1.0).\n\n"
        f"Return JSON ONLY with keys 'choice', 'confidence', 'probabilities' (mapping esi_1..esi_5 to floats)."
    )

    models_to_try = [settings.gemini_model]
    if settings.gemini_model != "gemini-2.5-flash":
        models_to_try.append("gemini-2.5-flash")

    last_exc = None
    for model_name in models_to_try:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw = json.loads(resp.text)
            return {
                "choice": raw.get("choice"),
                "confidence": float(raw.get("confidence", 0.8)),
                "probabilities": dict(raw["probabilities"]),
                "model": model_name,
            }
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise JevError("Gemini acuity call returned no response")


def score_with_gemini(
    chart: ExtractionResult,
    settings: Optional[Settings] = None,
    order: str = "forward",
) -> JevOutcome:
    """Score acuity with Gemini when TypeSafe Jev is unavailable."""
    settings = settings or get_settings()
    if not settings.gemini_live_ready:
        raise JevError("GOOGLE_API_KEY is not set (or offline mode is on)")
    start = now()
    raw = call_with_timeout(_gemini_acuity_call, settings.gemini_timeout_s + 1.0, chart.jev_state(), settings, order)
    vector = probability_vector(raw["probabilities"])
    return JevOutcome(
        probabilities=vector,
        confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
        choice=raw.get("choice"),
        source="gemini_acuity",
        latency_ms=elapsed_ms(start),
        model=raw.get("model", settings.gemini_model),
        prompt_version="RP-G1-acuity v1",
        option_order=order,
    )


def score(
    chart: ExtractionResult,
    *,
    fixture_id: Optional[str] = None,
    mode: str = "auto",
    order: str = "forward",
) -> JevOutcome:
    """Probabilities for this chart.

    mode "auto":    live Jev if a key is set; otherwise Gemini acuity if available;
                    otherwise (or if calls fail) the stored fixture vector when known,
                    otherwise the safety hold.
    mode "offline": never call the API.
    mode "outage":  simulate an outage: always the safety hold (no probabilities).
    """
    if mode not in ("auto", "offline", "outage"):
        raise ValueError("mode must be one of ('auto', 'offline', 'outage')")
    settings = get_settings()
    start = now()

    def hold(note: str) -> JevOutcome:
        return JevOutcome(None, None, None, "regex_hold", elapsed_ms(start), note=note, option_order=order)

    if mode == "outage":
        return hold("Simulated API outage: no probabilities, conservative ESI 2 safety hold.")

    note: Optional[str] = None
    if mode == "auto" and settings.jev_live_ready:
        try:
            return score_live(chart, settings, order)
        except (ApiTimeout, JevError) as exc:
            note = f"Jev call failed: {mask_secrets(str(exc), settings.typesafe_api_key)[:200]}"
        except Exception as exc:  # SDK, network, auth: never crash the intake flow
            note = (
                f"Jev call failed ({type(exc).__name__}): "
                f"{mask_secrets(str(exc), settings.typesafe_api_key)[:200]}"
            )
    elif mode == "offline" or settings.force_offline:
        note = "Offline mode: no API call was made."
    else:
        note = "No TYPESAFE_API_KEY set: no API call was made."

    if mode == "auto" and settings.gemini_live_ready and not fixture_id:
        try:
            outcome = score_with_gemini(chart, settings, order)
            if note:
                outcome.note = f"{note}; fallback to live Gemini acuity scoring"
            return outcome
        except Exception as exc:
            gem_err = f"Gemini acuity call failed ({type(exc).__name__}): {str(exc)[:150]}"
            note = f"{note}; {gem_err}" if note else gem_err

    if fixture_id:
        return JevOutcome(
            probabilities=fixtures.load_probabilities(fixture_id),
            confidence=None,
            choice=None,
            source="fixture_probs",
            latency_ms=elapsed_ms(start),
            note=note,
            option_order=order,
        )
    return hold((note or "") + " No stored probabilities for this case: conservative ESI 2 safety hold.")


# ---------------------------------------------------------------------------
# Sanity checks (HACKATHON_TEST_DRIVE.md section 9.1, "Sanity checks before trusting RP-J1")
# ---------------------------------------------------------------------------

def _argmax(vector: list[float]) -> int:
    return max(range(5), key=lambda i: vector[i]) + 1


def run_sanity(fixture_ids=("A", "B", "C"), repeats: int = 3, spread_limit: float = 0.05) -> dict:
    """Run the four RP-J1 sanity checks against live Jev, using the STORED charts (so Gemini is not involved).

    Needs TYPESAFE_API_KEY. Returns {"runs": ..., "checks": [...]} where each check has name, passed, detail.
    """
    settings = get_settings()
    runs: dict[str, dict[str, list[list[float]]]] = {}
    models: set[str] = set()
    for fid in fixture_ids:
        chart = fixtures.load_chart(fid)
        runs[fid] = {}
        for order in ORDERS:
            vectors = []
            for _ in range(repeats):
                outcome = score_live(chart, settings, order)
                vectors.append(outcome.probabilities)
                if outcome.model:
                    models.add(outcome.model)
            runs[fid][order] = vectors

    def mean(vectors: list[list[float]]) -> list[float]:
        return [sum(v[i] for v in vectors) / len(vectors) for i in range(5)]

    fwd = {fid: mean(runs[fid]["forward"]) for fid in fixture_ids}
    rev = {fid: mean(runs[fid]["reversed"]) for fid in fixture_ids}
    checks = []

    if "A" in fwd and "B" in fwd:
        a_high, b_high = sum(fwd["A"][:2]), sum(fwd["B"][:2])
        checks.append({
            "name": "1. Chest pain (A) has more mass on ESI 1+2 than ankle sprain (B)",
            "passed": a_high > b_high,
            "detail": f"A = {a_high:.3f}, B = {b_high:.3f}",
        })
    if "B" in fwd:
        tier = _argmax(fwd["B"])
        checks.append({
            "name": "2. Ankle sprain (B) is most likely ESI 4 or ESI 5",
            "passed": tier in (4, 5),
            "detail": f"most likely ESI {tier}, vector {[round(x, 3) for x in fwd['B']]}",
        })
    flips = {fid: (_argmax(fwd[fid]), _argmax(rev[fid])) for fid in fixture_ids}
    checks.append({
        "name": "3. Reversing the option order does not change the most likely tier",
        "passed": all(a == b for a, b in flips.values()),
        "detail": ", ".join(f"{fid}: {a} vs {b}" for fid, (a, b) in flips.items()),
    })
    spreads = {
        fid: max(
            max(v[i] for v in runs[fid]["forward"]) - min(v[i] for v in runs[fid]["forward"]) for i in range(5)
        )
        for fid in fixture_ids
    }
    checks.append({
        "name": f"4. Repeated runs are stable (largest spread per tier <= {spread_limit})",
        "passed": all(s <= spread_limit for s in spreads.values()),
        "detail": ", ".join(f"{fid}: {s:.3f}" for fid, s in spreads.items()),
    })
    return {"runs": runs, "mean_forward": fwd, "mean_reversed": rev, "models": sorted(models), "checks": checks}
