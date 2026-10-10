"""Smoke test of the Streamlit app with Streamlit's own headless test runner. No browser, no network, no keys."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")   # AppTest resolves relative paths against the test file


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIAGE_SKIP_WARMUP", "1")      # do not load Whisper in the test
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [w.value for w in at.warning]
    parts += [e.value for e in at.error] + [s.value for s in at.success]   # the label banner is one of these
    parts += [m.label + " " + str(m.value) for m in at.metric]
    return "\n".join(str(p) for p in parts)


def _turn_audio_off(at):
    for toggle in at.toggle:
        toggle.set_value(False)
    return at.run()


def test_app_starts_with_no_keys_and_says_so(app):
    assert "Administrative intake aid" in _text(app)
    assert any("Missing keys are fine" in i.value for i in app.sidebar.info)


def test_chest_pain_case_runs_and_shows_the_flag(app):
    _turn_audio_off(app)
    app.button[0].click().run()
    assert not app.exception, [e.value for e in app.exception]
    text = _text(app)
    assert "FIXTURE PROBABILITIES - NOT MODEL OUTPUT" in text
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["SUGGESTED REVIEW TIER"] == "ESI 2"
    assert metrics["Model's most likely tier"] == "ESI 3"
    assert "raised the tier" in text


def test_ankle_case_stays_at_esi_4(app):
    app.selectbox[0].set_value("B").run()
    _turn_audio_off(app)
    app.button[0].click().run()
    assert not app.exception
    assert {m.label: m.value for m in app.metric}["SUGGESTED REVIEW TIER"] == "ESI 4"


def test_outage_mode_shows_the_safety_hold(app):
    app.sidebar.radio[0].set_value("outage").run()
    _turn_audio_off(app)
    app.button[0].click().run()
    assert not app.exception
    assert "OFFLINE SAFETY HOLD - SUGGESTED REVIEW ESI 2" in _text(app)


def test_custom_transcript_without_keys_is_a_hold(app):
    app.selectbox[0].set_value("custom").run()
    assert app.button[0].disabled                      # nothing typed yet
    app.text_area[0].set_value("Me duele el pecho y me falta el aire.").run()
    app.button[0].click().run()
    assert not app.exception
    assert "OFFLINE SAFETY HOLD" in _text(app)


def test_queue_tab_shows_the_corrected_numbers(app):
    labels = {m.label: m.value for m in app.metric}
    assert labels["Manual: average wait"] == "25.7 min"
    assert labels["Automated: average wait"] == "9 s"
    assert labels["Wait reduction"] == "99.4%"
