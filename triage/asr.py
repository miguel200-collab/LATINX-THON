"""Step 1: audio -> Spanish transcript, locally, with faster-whisper. It only writes the words.

Gemini never hears the audio; Deepgram Nova is the swap-in at the real event. The model is
cached inside the project (.cache/huggingface, see config.py), so after one download it runs offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config  # noqa: F401  (sets HF_HOME before faster_whisper is imported)
from .config import get_settings
from .fixtures import normalize_text
from .util import elapsed_ms, now

# A hint of the vocabulary to expect. It nudges the decoder toward dialect words it might otherwise mishear.
# Caveat: on unclear audio a prompt can leak words into the output, so compare against a fixture.
INITIAL_PROMPT = (
    "Paciente hispanohablante en urgencias. Palabras posibles: apretón en el pecho, patatús, sofocón, "
    "falta de aire, brazo izquierdo, mandíbula, sudor frío."
)

_MODELS: dict[str, object] = {}


@dataclass
class AsrOutcome:
    text: str
    latency_ms: float            # transcription time only
    load_ms: float               # model load time (0 if already loaded)
    model: str
    audio_seconds: Optional[float]
    language: str
    language_probability: Optional[float]

    @property
    def total_ms(self) -> float:
        return round(self.latency_ms + self.load_ms, 1)


def is_model_cached(model_size: Optional[str] = None) -> bool:
    """True if the Whisper model is already on disk (so no download is needed)."""
    from faster_whisper.utils import download_model

    size = model_size or get_settings().whisper_model
    try:
        download_model(size, local_files_only=True)
        return True
    except Exception:
        return False


def prefetch_model(model_size: Optional[str] = None) -> str:
    """Download the model into the project cache (needs internet once). Returns the local path."""
    from faster_whisper.utils import download_model

    return download_model(model_size or get_settings().whisper_model)


def _load(model_size: str):
    if model_size not in _MODELS:
        from faster_whisper import WhisperModel

        # Without local_files_only, WhisperModel() asks huggingface.co about the model on every start,
        # even when it is cached, and crashes with no network. When cached, never touch the network.
        _MODELS[model_size] = WhisperModel(
            model_size, device="cpu", compute_type="int8", local_files_only=is_model_cached(model_size)
        )
        return _MODELS[model_size], True
    return _MODELS[model_size], False


def transcribe(
    audio_path: str | Path,
    *,
    model_size: Optional[str] = None,
    language: Optional[str] = None,
    initial_prompt: Optional[str] = INITIAL_PROMPT,
) -> AsrOutcome:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    size = model_size or get_settings().whisper_model

    load_start = now()
    model, loaded_now = _load(size)
    load_ms = elapsed_ms(load_start) if loaded_now else 0.0

    start = now()
    segments, info = model.transcribe(
        str(path), language=language, beam_size=5, initial_prompt=initial_prompt, condition_on_previous_text=False
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    text = re.sub(r"\s+", " ", text)
    return AsrOutcome(
        text=text,
        latency_ms=elapsed_ms(start),
        load_ms=load_ms,
        model=f"whisper {size}",
        audio_seconds=round(float(info.duration), 2) if getattr(info, "duration", None) else None,
        language=info.language,
        language_probability=round(float(info.language_probability), 3) if info.language_probability else None,
    )


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Word error rate after lowercasing and removing accents and punctuation. 0.0 is a perfect match."""
    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)
