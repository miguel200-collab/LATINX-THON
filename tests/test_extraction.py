"""Extraction logic with a faked Gemini call. No network, no keys."""

import json

import pytest

from triage import extraction as ex
from triage import fixtures as fx
from triage.checks import check_gold
from triage.util import ApiTimeout


def _good_json(fid="A"):
    return json.loads((fx.FIXTURES_DIR / "charts" / f"{fid}.json").read_text(encoding="utf-8"))


@pytest.fixture
def live(monkeypatch):
    """Pretend a Google key exists."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")


# --- regex safety hold -------------------------------------------------------

def test_regex_hold_finds_red_flags_in_the_chest_pain_clip():
    chart = ex.regex_hold_chart(fx.load_transcript("A"))
    assert {"chest_pain", "dyspnea", "diaphoresis"} <= set(chart.red_flag_symptoms)
    assert {"left_arm", "jaw"} == set(chart.radiation)
    assert chart.location == "chest"


def test_regex_hold_maps_dialect_words():
    chart = ex.regex_hold_chart(fx.load_transcript("A_long"))
    assert "syncope" in chart.red_flag_symptoms          # "patatús"
    mexican = ex.regex_hold_chart("Siento un sofocón recio y no puedo respirar.")
    assert "dyspnea" in mexican.red_flag_symptoms        # "sofocón"


def test_regex_hold_finds_nothing_for_the_ankle_sprain():
    assert ex.regex_hold_chart(fx.load_transcript("B")).red_flag_symptoms == []


def test_regex_hold_quotes_are_real_text_from_the_transcript():
    outcome = ex.extract(fx.load_transcript("A") + " Tengo sangrado.", mode="outage")
    assert outcome.source == "regex_hold"
    assert outcome.unverified_quotes == []


# --- JSON parsing -------------------------------------------------------------

def test_parse_json_strips_markdown_fences():
    assert ex.parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_finds_object_inside_prose():
    assert ex.parse_json_text('Here you go: {"a": 2} Hope that helps.') == {"a": 2}


def test_parse_json_rejects_garbage():
    with pytest.raises(ValueError):
        ex.parse_json_text("no json here")


# --- live path with a faked call ---------------------------------------------

def test_live_success_returns_gemini_source_and_passes_gold(live, monkeypatch):
    monkeypatch.setattr(ex, "_gemini_call", lambda t, s, extra="": json.dumps(_good_json("A")))
    out = ex.extract(fx.load_transcript("A"))
    assert out.source == "gemini"
    assert out.model == "gemini-3.8-flash"
    assert out.prompt_version == "RP-G1 v1"
    assert check_gold(out.chart, fx.load_gold("A")) == []
    assert out.unverified_quotes == []


def test_live_markdown_fenced_output_is_accepted(live, monkeypatch):
    fenced = "```json\n" + json.dumps(_good_json("B")) + "\n```"
    monkeypatch.setattr(ex, "_gemini_call", lambda t, s, extra="": fenced)
    assert ex.extract(fx.load_transcript("B")).source == "gemini"


def test_invalid_first_answer_is_retried_once(live, monkeypatch):
    calls = []

    def fake(t, s, extra=""):
        calls.append(extra)
        return "not json at all" if len(calls) == 1 else json.dumps(_good_json("A"))

    monkeypatch.setattr(ex, "_gemini_call", fake)
    out = ex.extract(fx.load_transcript("A"))
    assert out.source == "gemini"
    assert len(calls) == 2 and calls[0] == "" and "could not be used" in calls[1]


def test_schema_violation_is_retried_then_falls_back_to_fixture(live, monkeypatch):
    bad = _good_json("A")
    bad["quality"] = "stabbing"  # not in the closed list
    monkeypatch.setattr(ex, "_gemini_call", lambda t, s, extra="": json.dumps(bad))
    out = ex.extract(fx.load_transcript("A"))
    assert out.source == "fixture_chart"
    assert "failed validation" in out.note


def test_timeout_falls_back_to_regex_hold_for_unknown_text(live, monkeypatch):
    def slow(t, s, extra=""):
        raise ApiTimeout("no response within 8.0s")

    monkeypatch.setattr(ex, "_gemini_call", slow)
    out = ex.extract("Me duele mucho el pecho y me falta el aire.")
    assert out.source == "regex_hold"
    assert "chest_pain" in out.chart.red_flag_symptoms
    assert "no response" in out.note


def test_api_key_is_never_leaked_into_the_note(live, monkeypatch):
    def boom(t, s, extra=""):
        raise RuntimeError("401 for key test-key-123 at https://example.test")

    monkeypatch.setattr(ex, "_gemini_call", boom)
    out = ex.extract(fx.load_transcript("B"))
    assert "test-key-123" not in out.note
    assert "***" in out.note


# --- modes -------------------------------------------------------------------

def test_no_key_uses_stored_fixture_chart_for_known_transcript():
    out = ex.extract(fx.load_transcript("A"))
    assert out.source == "fixture_chart"
    assert "GOOGLE_API_KEY" in out.note
    assert out.chart.quality == "crushing_pressure"


def test_no_key_and_unknown_text_uses_regex_hold():
    assert ex.extract("Me duele la rodilla desde ayer.").source == "regex_hold"


def test_offline_mode_never_calls_the_api(live, monkeypatch):
    def forbidden(t, s, extra=""):
        raise AssertionError("API must not be called in offline mode")

    monkeypatch.setattr(ex, "_gemini_call", forbidden)
    assert ex.extract(fx.load_transcript("C"), mode="offline").source == "fixture_chart"


def test_triage_offline_env_blocks_api(live, monkeypatch):
    monkeypatch.setenv("TRIAGE_OFFLINE", "1")

    def forbidden(t, s, extra=""):
        raise AssertionError("API must not be called when TRIAGE_OFFLINE=1")

    monkeypatch.setattr(ex, "_gemini_call", forbidden)
    assert ex.extract(fx.load_transcript("A")).source == "fixture_chart"


def test_outage_mode_always_gives_the_hold_even_for_a_fixture(live):
    out = ex.extract(fx.load_transcript("A"), mode="outage")
    assert out.source == "regex_hold"
    assert "Simulated" in out.note


def test_bad_mode_is_rejected():
    with pytest.raises(ValueError):
        ex.extract("hola", mode="turbo")


def test_real_sdk_call_is_built_correctly_up_to_the_network(live, monkeypatch):
    """Uses the real google-genai client and config classes; only the HTTP call is captured."""
    from google.genai import models as genai_models

    captured = {}

    class FakeResponse:
        text = json.dumps(_good_json("A"))

    def fake_generate(self, *, model, contents, config=None):
        captured.update(model=model, contents=contents, config=config)
        return FakeResponse()

    monkeypatch.setattr(genai_models.Models, "generate_content", fake_generate)
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "low")
    out = ex.extract(fx.load_transcript("A"))

    assert out.source == "gemini"
    assert captured["model"] == "gemini-3.8-flash"
    assert captured["contents"] == fx.load_transcript("A")
    cfg = captured["config"]
    assert cfg.response_mime_type == "application/json"
    assert "never assign a triage level" in cfg.system_instruction
    assert cfg.thinking_config.thinking_level.name == "LOW"


def test_prompt_contains_the_dialect_guide_and_the_no_diagnosis_rule():
    from triage.prompts import GEMINI_SYSTEM_PROMPT as p

    for needle in ("patatús", "sofocón", "apretón en el pecho", "JSON only", "never assign a triage level", "Never guess"):
        assert needle in p
    for value in ("crushing_pressure", "diaphoresis", "upper_abdomen", "left_arm"):
        assert value in p
