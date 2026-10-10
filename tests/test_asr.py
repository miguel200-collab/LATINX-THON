"""Speech-to-text. The model tests are slow (they load Whisper) and skip themselves if it is not downloaded."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triage import asr
from triage import fixtures as fx

ROOT = Path(__file__).resolve().parent.parent


def test_word_error_rate_basics():
    assert asr.word_error_rate("me duele el pecho", "me duele el pecho") == 0.0
    assert asr.word_error_rate("me duele el pecho", "Me duele el pecho!") == 0.0       # case/punctuation ignored
    assert asr.word_error_rate("apretón en el pecho", "apreton en el pecho") == 0.0    # accents ignored
    assert asr.word_error_rate("a b c d", "a b c e") == pytest.approx(0.25)
    assert asr.word_error_rate("a b", "") == 1.0
    assert asr.word_error_rate("", "") == 0.0


def test_missing_audio_file_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        asr.transcribe(tmp_path / "nope.wav")


def test_prompt_hint_contains_the_dialect_words():
    for word in ("patatús", "sofocón", "apretón en el pecho"):
        assert word in asr.INITIAL_PROMPT


needs_model = pytest.mark.skipif(not asr.is_model_cached("small"), reason="Whisper 'small' is not downloaded")


@pytest.mark.slow
@needs_model
def test_transcribes_the_demo_clip_with_no_network_at_all():
    """Runs in a fresh process with the network disabled, like a laptop on bad conference Wi-Fi."""
    code = (
        "import json; from triage import asr, fixtures as fx;"
        "o = asr.transcribe(fx.audio_path('A'));"
        "print('RESULT ' + json.dumps({'text': o.text, 'wer': asr.word_error_rate(fx.load_transcript('A'), o.text),"
        " 'lang': o.language, 'seconds': o.audio_seconds, 'ms': o.latency_ms}))"
    )
    env = dict(os.environ, HF_HUB_OFFLINE="1", HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=240)
    assert done.returncode == 0, done.stderr[-800:]
    result = json.loads([ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")][0][7:])
    assert result["lang"] == "es"
    assert 14 < result["seconds"] < 17                  # the demo clip is about 15 seconds
    assert result["wer"] < 0.25, result["text"]
    text = result["text"].lower()
    assert "apretón" in text and "brazo izquierdo" in text and "mandíbula" in text
