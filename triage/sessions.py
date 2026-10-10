"""Patient sessions behind the web screens.

A session collects the patient's answers (voice notes transcribed by local Whisper, or typed text),
recomputes which questions are green after every answer, and on submit runs the full pipeline
(Gemini -> Jev -> loss -> PDF + JSON). The nurse then opens it, confirms or corrects each line,
and enters the official ESI, which produces a second, "confirmed" PDF.

Everything is stored under output/sessions/<id>/ so a server restart keeps the queue.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from . import config, fixtures
from .coverage import compute_state
from .pdf_sheet import SheetData, build_sheet_pdf
from .pipeline import run_pipeline
from .questions import BY_ID, QUESTION_IDS
from .readback import readback_es
from .schemas import QUOTE_FIELDS, ExtractionResult, TriageFlag

STATUS_ORDER = {"waiting": 0, "in_review": 1, "confirmed": 2}


class SessionError(Exception):
    """Bad request against a session (unknown question, wrong state, bad confirmation)."""


class NotFound(SessionError):
    pass


def _now() -> float:
    return time.time()


class SessionStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sessions: dict[str, dict] = {}
        for path in sorted(self.root.glob("*/session.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._sessions[data["id"]] = data
            except (OSError, ValueError, KeyError):
                continue

    # ----------------------------------------------------------------- basics
    def _dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _save(self, s: dict) -> None:
        d = self._dir(s["id"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "session.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, session_id: str) -> dict:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                raise NotFound(f"no session {session_id!r}")
            return s

    def create(self, fixture_id: Optional[str] = None) -> dict:
        if fixture_id is not None and fixture_id not in fixtures.FIXTURE_IDS:
            raise SessionError(f"unknown fixture {fixture_id!r}")
        with self._lock:
            sid = uuid.uuid4().hex[:6]
            while sid in self._sessions:
                sid = uuid.uuid4().hex[:6]
            s = {
                "id": sid, "created_at": _now(), "status": "in_progress", "fixture_id": fixture_id,
                "answers": [], "state": compute_state([]), "submitted_at": None, "opened_at": None,
                "result": None, "readback_es": None, "confirmation": None,
            }
            self._sessions[sid] = s
            self._save(s)
            return s

    def answer_dir(self, session_id: str) -> Path:
        d = self._dir(session_id) / "answers"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ----------------------------------------------------------------- answers
    def add_answer(self, session_id: str, question_id: str, text: str, source: str,
                   audio_file: Optional[str] = None, asr_ms: Optional[float] = None) -> dict:
        if question_id not in BY_ID:
            raise SessionError(f"unknown question {question_id!r}")
        text = (text or "").strip()
        if not text:
            raise SessionError("empty answer")
        with self._lock:
            s = self.get(session_id)
            if s["status"] != "in_progress":
                raise SessionError("this intake was already sent")
            s["answers"].append({
                "question_id": question_id, "text": text[:2000], "source": source,
                "audio_file": audio_file, "asr_ms": asr_ms, "at": _now(),
            })
            s["state"] = compute_state(s["answers"])
            self._save(s)
            return s

    def transcript(self, s: dict) -> str:
        """All answers in question order: what Gemini reads."""
        order = {qid: i for i, qid in enumerate(QUESTION_IDS)}
        answers = sorted(s["answers"], key=lambda a: (order.get(a["question_id"], 99), a["at"]))
        return "\n".join(a["text"] for a in answers)

    # ----------------------------------------------------------------- submit (runs the pipeline)
    def submit(self, session_id: str, mode: str = "auto") -> dict:
        with self._lock:
            s = self.get(session_id)
            if s["status"] != "in_progress":
                return s
            if not s["answers"]:
                raise SessionError("no answers yet")
            text = self.transcript(s)
        result = run_pipeline(
            transcript=text, fixture_id=s["fixture_id"], mode=mode,
            out_dir=self._dir(session_id), case_label=f"Patient {session_id}",
        )
        with self._lock:
            data = result.to_dict()
            data["files"] = {"pdf": result.pdf_path.name, "json": result.json_path.name}
            s["result"] = data
            s["readback_es"] = readback_es(result.extraction.chart)
            s["status"] = "waiting"
            s["submitted_at"] = _now()
            self._save(s)
            return s

    # ----------------------------------------------------------------- nurse side
    def open(self, session_id: str) -> dict:
        with self._lock:
            s = self.get(session_id)
            if s["status"] == "waiting":
                s["status"] = "in_review"
                s["opened_at"] = _now()
                self._save(s)
            return s

    def confirm(self, session_id: str, official_esi: int, fields: dict, readback_seconds: Optional[float]) -> dict:
        if official_esi not in (1, 2, 3, 4, 5):
            raise SessionError("official_esi must be 1 to 5")
        clean: dict[str, dict] = {}
        for key, val in (fields or {}).items():
            if key not in QUOTE_FIELDS:
                raise SessionError(f"unknown field {key!r}")
            status = (val or {}).get("status", "ok")
            if status not in ("ok", "corrected"):
                raise SessionError("field status must be 'ok' or 'corrected'")
            value = str((val or {}).get("value", "")).strip()[:300]
            if status == "corrected" and not value:
                raise SessionError(f"a correction for {key} needs a value")
            clean[key] = {"status": status, "value": value}
        with self._lock:
            s = self.get(session_id)
            if s["result"] is None:
                raise SessionError("this intake has not been sent yet")
            if readback_seconds is None and s.get("opened_at"):
                readback_seconds = round(_now() - s["opened_at"], 1)
            confirmation = {
                "official_esi": official_esi, "fields": clean,
                "readback_seconds": None if readback_seconds is None else round(float(readback_seconds), 1),
                "confirmed_at": _now(), "pdf": None,
            }
            pdf = self._dir(session_id) / f"confirmed_{session_id}.pdf"
            build_sheet_pdf(self._sheet(s, confirmation), pdf)
            confirmation["pdf"] = pdf.name
            s["confirmation"] = confirmation
            s["status"] = "confirmed"
            self._save(s)
            return s

    def _sheet(self, s: dict, confirmation: Optional[dict]) -> SheetData:
        r = s["result"]
        return SheetData(
            case_label=r["case"], arrival=r["arrival"], headline_label=r["labels"]["headline"],
            label_kind=r["labels"]["kind"], step_lines=r["labels"]["steps"],
            chart=ExtractionResult.model_validate(r["extraction"]["chart"]),
            flag=TriageFlag.model_validate(r["flag"]),
            unverified_quotes=r["extraction"]["unverified_quotes"], confirmation=confirmation,
        )

    def pdf_path(self, session_id: str, kind: str = "intake") -> Path:
        s = self.get(session_id)
        if kind == "confirmed":
            if not s.get("confirmation"):
                raise SessionError("not confirmed yet")
            return self._dir(session_id) / s["confirmation"]["pdf"]
        if not s.get("result"):
            raise SessionError("not sent yet")
        return self._dir(session_id) / s["result"]["files"]["pdf"]

    # ----------------------------------------------------------------- views
    def all(self) -> list[dict]:
        with self._lock:
            return list(self._sessions.values())

    def summary(self, s: dict) -> dict:
        r = s.get("result") or {}
        flag = r.get("flag") or {}
        chart = (r.get("extraction") or {}).get("chart") or {}
        since = s.get("submitted_at") or s["created_at"]
        end = (s.get("confirmation") or {}).get("confirmed_at") or _now()
        return {
            "id": s["id"], "status": s["status"], "created_at": s["created_at"], "submitted_at": s.get("submitted_at"),
            "wait_seconds": round(end - since), "answers": len(s["answers"]),
            "suggested_review_tier": flag.get("suggested_review_tier"), "raw_argmax_tier": flag.get("raw_argmax_tier"),
            "override_triggered": flag.get("override_triggered"),
            "label_kind": (r.get("labels") or {}).get("kind"), "headline": (r.get("labels") or {}).get("headline"),
            "red_flags": chart.get("red_flag_symptoms", []), "location": chart.get("location"),
            "official_esi": (s.get("confirmation") or {}).get("official_esi"),
            "fixture_id": s.get("fixture_id"),
        }

    def queue(self) -> list[dict]:
        with self._lock:
            sent = [self.summary(s) for s in self._sessions.values() if s["status"] in STATUS_ORDER]
        return sorted(sent, key=lambda x: (STATUS_ORDER[x["status"]], x["suggested_review_tier"] or 9, x["submitted_at"] or 0))

    def public(self, s: dict) -> dict:
        """What the patient screen may see: questions state only. Never the tier or the chart."""
        return {"id": s["id"], "status": s["status"], "state": s["state"],
                "answered": [a["question_id"] for a in s["answers"]]}

    def detail(self, s: dict) -> dict:
        """What the nurse screen sees."""
        out = dict(s)
        out["summary"] = self.summary(s)
        out["questions"] = [{"id": q, "es": BY_ID[q]["es"], "en": BY_ID[q]["en"]} for q in QUESTION_IDS]
        return out


_stores: dict[Path, SessionStore] = {}
_stores_lock = threading.Lock()


def get_store() -> SessionStore:
    """One store per output folder (tests point OUTPUT_DIR at a temp folder)."""
    root = Path(config.OUTPUT_DIR) / "sessions"
    with _stores_lock:
        if root not in _stores:
            _stores[root] = SessionStore(root)
        return _stores[root]
