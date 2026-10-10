"""Settings read from the environment (and a git-ignored .env file in the project root).

Only two values are needed to go fully live: GOOGLE_API_KEY and TYPESAFE_API_KEY.
Everything else has a default. See .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"

load_dotenv(ROOT / ".env")

# Keep the Whisper model cache inside the project so a fresh checkout is self-contained
# (and so restricted sandboxes can write to it). Must be set before faster_whisper is imported.
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _key(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None
    typesafe_api_key: str | None
    gemini_model: str
    jev_model: str
    whisper_model: str
    gemini_thinking_level: str | None
    gemini_timeout_s: float
    jev_timeout_s: float
    c_under: float
    c_over: float
    force_offline: bool

    @property
    def gemini_live_ready(self) -> bool:
        return bool(self.google_api_key) and not self.force_offline

    @property
    def jev_live_ready(self) -> bool:
        return bool(self.typesafe_api_key) and not self.force_offline


def get_settings() -> Settings:
    """Read settings fresh each call so tests and the UI can change the environment."""
    return Settings(
        google_api_key=_key("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        typesafe_api_key=_key("TYPESAFE_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.8-flash",
        jev_model=os.getenv("JEV_MODEL", "").strip() or "jev-latest",
        whisper_model=os.getenv("WHISPER_MODEL", "").strip() or "small",
        gemini_thinking_level=(os.getenv("GEMINI_THINKING_LEVEL", "").strip().upper() or None),
        gemini_timeout_s=_float("GEMINI_TIMEOUT_S", 15.0),
        jev_timeout_s=_float("JEV_TIMEOUT_S", 5.0),
        c_under=_float("C_UNDER", 10.0),
        c_over=_float("C_OVER", 1.0),
        force_offline=os.getenv("TRIAGE_OFFLINE", "0").strip() in ("1", "true", "True", "yes"),
    )
