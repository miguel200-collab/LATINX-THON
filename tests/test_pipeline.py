"""End-to-end intake with no network: labels, tiers, files, and the blank official ESI."""

import json
import re

import pypdf
import pytest

from triage import asr as asr_module
from triage import extraction as ex
from triage import fixtures as fx
from triage import jev
from triage.pipeline import (
    FIXTURE_CHART_LABEL,
    FIXTURE_PROBS_LABEL,
    HOLD_LABEL,
    PipelineError,
    run_pipeline,
)
from triage.util import ApiTimeout


def pdf_text(path):
    reader = pypdf.PdfReader(str(path))
    return len(reader.pages), re.sub(r"\s+", " ", "\n".join(p.extract_text() for p in reader.pages))


def fake_jev(vector=(0.02, 0.18, 0.60, 0.15, 0.05), confidence=0.7):
    probs = {f"esi_{i + 1}": p for i, p in enumerate(vector)}
    return lambda state, settings, order="forward": {
        "choice": "esi_3", "confidence": confidence, "probabilities": probs, "model": "jev-1.13.0"}


def fake_gemini(fid):
    text = (fx.FIXTURES_DIR / "charts" / f"{fid}.json").read_text(encoding="utf-8")
    return lambda transcript, settings, extra="": text


# --- offline, stored fixtures --------------------------------------------------------------------

def test_chest_pain_fixture_offline_flags_esi_2_and_labels_the_fixture(tmp_path):
    r = run_pipeline(fixture_id="A", mode="offline", out_dir=tmp_path)
    assert r.flag.raw_argmax_tier == 3 and r.flag.suggested_review_tier == 2 and r.flag.override_triggered
    assert r.headline_label == FIXTURE_PROBS_LABEL and r.label_kind == "fixture"
    assert r.transcript_source == "fixture_text" and r.transcript == fx.load_transcript("A")
    pages, text = pdf_text(r.pdf_path)
    assert pages == 1 and FIXTURE_PROBS_LABEL in text and "SUGGESTED REVIEW TIER: ESI 2" in text


def test_ankle_fixture_stays_at_esi_4(tmp_path):
    r = run_pipeline(fixture_id="B", mode="offline", out_dir=tmp_path)
    assert r.flag.suggested_review_tier == 4 and not r.flag.override_triggered


def test_ambiguous_fixture_is_escalated(tmp_path):
    r = run_pipeline(fixture_id="C", mode="offline", out_dir=tmp_path)
    assert r.flag.raw_argmax_tier == 4 and r.flag.suggested_review_tier == 2


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_json_is_saved_next_to_the_pdf_and_official_esi_is_blank(fid, tmp_path):
    r = run_pipeline(fixture_id=fid, mode="offline", out_dir=tmp_path)
    assert r.json_path.parent == r.pdf_path.parent and r.json_path.stem == r.pdf_path.stem
    data = json.loads(r.json_path.read_text(encoding="utf-8"))
    assert data["official_esi"] is None
    assert data["labels"]["headline"] == r.headline_label
    assert data["flag"]["suggested_review_tier"] == r.flag.suggested_review_tier
    assert data["extraction"]["chart"]["location"] == fx.load_chart(fid).location
    assert "Not a diagnosis" in data["disclaimer"]
    for key in ("gemini", "jev", "loss", "pdf", "total"):
        assert key in data["latency_ms"]


def test_known_typed_transcript_uses_the_stored_chart(tmp_path):
    r = run_pipeline(transcript=fx.load_transcript("B"), mode="offline", out_dir=tmp_path)
    assert r.fixture_id == "B" and r.transcript_source == "typed"
    assert r.flag.suggested_review_tier == 4


def test_loss_weights_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("C_UNDER", "1")  # symmetric costs: the safety override disappears
    r = run_pipeline(fixture_id="A", mode="offline", out_dir=tmp_path)
    assert r.flag.suggested_review_tier == 3 and not r.flag.override_triggered


# --- safety hold ------------------------------------------------------------------------------------

def test_unknown_text_without_keys_is_a_safety_hold(tmp_path):
    r = run_pipeline(transcript="Me duele el pecho y me falta el aire.", out_dir=tmp_path)
    assert r.headline_label == HOLD_LABEL and r.label_kind == "hold"
    assert r.flag.suggested_review_tier == 2 and r.flag.probabilities is None and r.flag.source == "regex_hold"
    assert "chest_pain" in r.extraction.chart.red_flag_symptoms
    pages, text = pdf_text(r.pdf_path)
    assert pages == 1 and "No probabilities are available" in text


def test_outage_mode_forces_the_hold_even_for_a_fixture(tmp_path):
    r = run_pipeline(fixture_id="B", mode="outage", out_dir=tmp_path)   # a sprain, held at ESI 2 on purpose
    assert r.headline_label == HOLD_LABEL and r.flag.suggested_review_tier == 2
    assert r.scoring.source == "regex_hold" and r.extraction.source == "regex_hold"


# --- live paths (calls faked) -----------------------------------------------------------------------

def test_fully_live_run_is_labeled_live_with_model_names(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key-111")
    monkeypatch.setenv("TYPESAFE_API_KEY", "t-key-222")
    monkeypatch.setattr(ex, "_gemini_call", fake_gemini("A"))
    monkeypatch.setattr(jev, "_jev_call", fake_jev())
    r = run_pipeline(transcript=fx.load_transcript("A"), out_dir=tmp_path)
    assert r.label_kind == "live"
    assert r.headline_label == "LIVE: typed transcript + gemini-3.8-flash + jev-1.13.0"
    assert r.flag.source == "jev" and r.flag.jev_confidence == pytest.approx(0.7)
    assert r.flag.suggested_review_tier == 2
    _, text = pdf_text(r.pdf_path)
    assert "LIVE: typed transcript + gemini-3.8-flash + jev-1.13.0" in text and "Jev confidence: 0.70" in text
    assert FIXTURE_PROBS_LABEL not in text
    # secrets never reach any output file
    for secret in ("g-key-111", "t-key-222"):
        assert secret not in r.json_path.read_text(encoding="utf-8")


def test_live_gemini_but_no_jev_key_labels_the_probabilities_as_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key-111")
    monkeypatch.setattr(ex, "_gemini_call", fake_gemini("A"))
    r = run_pipeline(fixture_id="A", out_dir=tmp_path)
    assert r.extraction.source == "gemini" and r.scoring.source == "fixture_probs"
    assert r.headline_label == FIXTURE_PROBS_LABEL


def test_gemini_timeout_on_a_fixture_falls_back_to_the_stored_chart_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key-111")
    monkeypatch.setenv("TYPESAFE_API_KEY", "t-key-222")
    monkeypatch.setattr(ex, "_gemini_call", lambda t, s, extra="": (_ for _ in ()).throw(ApiTimeout("no response within 8.0s")))
    monkeypatch.setattr(jev, "_jev_call", fake_jev())
    r = run_pipeline(fixture_id="A", out_dir=tmp_path)
    assert r.extraction.source == "fixture_chart" and r.scoring.source == "jev"
    assert r.headline_label == FIXTURE_CHART_LABEL
    _, text = pdf_text(r.pdf_path)
    assert "Gemini call failed" in text            # a failed live call is shown on the sheet


def test_jev_failure_falls_back_to_fixture_probabilities(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "t-key-222")
    monkeypatch.setattr(jev, "_jev_call", lambda s, st, o="forward": (_ for _ in ()).throw(RuntimeError("503")))
    r = run_pipeline(fixture_id="C", out_dir=tmp_path)
    assert r.scoring.source == "fixture_probs" and r.headline_label == FIXTURE_PROBS_LABEL
    assert r.flag.suggested_review_tier == 2


# --- audio path (speech-to-text faked) --------------------------------------------------------------

def _fake_asr(text):
    return lambda path, **kw: asr_module.AsrOutcome(
        text=text, latency_ms=2600.0, load_ms=0.0, model="whisper small",
        audio_seconds=15.5, language="es", language_probability=1.0)


def test_audio_path_uses_the_transcript_and_reports_the_stt_step(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_module, "transcribe", _fake_asr(fx.load_transcript("A")))
    r = run_pipeline(audio_path=fx.audio_path("A"), fixture_id="A", mode="offline", out_dir=tmp_path)
    assert r.transcript_source == "whisper" and r.latency_ms["asr"] == 2600.0
    assert r.step_lines[0].startswith("Speech-to-text: whisper small (live")
    assert r.extraction.unverified_quotes == []


def test_misheard_audio_marks_quotes_that_are_not_in_the_transcript(tmp_path, monkeypatch):
    heard = fx.load_transcript("C").replace("desde que cené me arde", "desde que se enemear de")
    monkeypatch.setattr(asr_module, "transcribe", _fake_asr(heard))
    r = run_pipeline(audio_path=fx.audio_path("C"), fixture_id="C", mode="offline", out_dir=tmp_path)
    assert {"onset", "provocation", "quality"} <= set(r.extraction.unverified_quotes)
    _, text = pdf_text(r.pdf_path)
    assert "not found in transcript" in text


def test_speech_to_text_failure_falls_back_to_the_fixture_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_module, "transcribe", lambda path, **kw: (_ for _ in ()).throw(RuntimeError("no model")))
    r = run_pipeline(audio_path=fx.audio_path("B"), fixture_id="B", mode="offline", out_dir=tmp_path)
    assert r.transcript_source == "fixture_text"
    assert any("Speech-to-text failed" in n for n in r.notes)


def test_speech_to_text_failure_without_a_fixture_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_module, "transcribe", lambda path, **kw: (_ for _ in ()).throw(RuntimeError("no model")))
    with pytest.raises(PipelineError):
        run_pipeline(audio_path=fx.audio_path("B"), mode="offline", out_dir=tmp_path)


def test_silent_audio_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_module, "transcribe", _fake_asr("   "))
    with pytest.raises(PipelineError):
        run_pipeline(audio_path=fx.audio_path("B"), fixture_id="B", mode="offline", out_dir=tmp_path)


# --- bad input ----------------------------------------------------------------------------------------

def test_nothing_to_process_is_an_error():
    with pytest.raises(PipelineError):
        run_pipeline()


def test_blank_transcript_is_an_error():
    with pytest.raises(PipelineError):
        run_pipeline(transcript="   ")


def test_bad_mode_is_rejected():
    with pytest.raises(ValueError):
        run_pipeline(fixture_id="A", mode="turbo")


def test_every_run_writes_its_own_files_even_inside_one_second(tmp_path):
    """Each run makes a new PDF+JSON pair; two quick runs of the same case must not overwrite each other."""
    names = {run_pipeline(fixture_id="A", mode="offline", out_dir=tmp_path).pdf_path.name for _ in range(5)}
    assert len(names) == 5
    assert len(list(tmp_path.glob("*.pdf"))) == 5 and len(list(tmp_path.glob("*.json"))) == 5


def test_make_pdf_false_writes_nothing(tmp_path):
    r = run_pipeline(fixture_id="A", mode="offline", make_pdf=False, out_dir=tmp_path)
    assert r.pdf_path is None and list(tmp_path.iterdir()) == []


# --- the real thing, end to end on this machine -----------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not asr_module.is_model_cached("small"), reason="Whisper 'small' is not downloaded")
def test_real_whisper_on_the_demo_clip_through_the_whole_pipeline(tmp_path):
    r = run_pipeline(audio_path=fx.audio_path("A"), fixture_id="A", mode="offline", out_dir=tmp_path)
    assert r.transcript_source == "whisper" and r.asr.language == "es"
    assert "apretón" in r.transcript.lower()
    assert r.flag.suggested_review_tier == 2
    pages, _ = pdf_text(r.pdf_path)
    assert pages == 1
