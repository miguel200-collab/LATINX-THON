"""Tests must never touch a real API, even if a .env with real keys exists, and must never write into the real output/ folder."""

import pytest


@pytest.fixture(autouse=True)
def _no_real_keys(monkeypatch):
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "TYPESAFE_API_KEY", "DEEPGRAM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TRIAGE_OFFLINE", "0")
    monkeypatch.delenv("GEMINI_THINKING_LEVEL", raising=False)
    monkeypatch.setenv("TRIAGE_SKIP_WARMUP", "1")      # the web server must not load Whisper in tests
    monkeypatch.delenv("TRIAGE_MODE", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)


@pytest.fixture(autouse=True)
def _private_output_folder(monkeypatch, tmp_path):
    """The pipeline and the app default to <project>/output. Point both at a throwaway folder."""
    import triage.config

    folder = tmp_path / "output"
    monkeypatch.setattr(triage.config, "OUTPUT_DIR", folder)
    try:
        import triage.pipeline
        monkeypatch.setattr(triage.pipeline, "OUTPUT_DIR", folder)
    except (ImportError, ModuleNotFoundError):
        pass
