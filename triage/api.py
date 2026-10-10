"""HTTP API and web pages: the patient chat, the nurse queue, and the judge page.

    uv run python -m triage.cli serve                    # http://localhost:8000
    cloudflared tunnel --url http://localhost:8000       # public https link for phones and judges

Pages: /  (judge page: both sides + benchmarks)   /p  (patient chat, phone)   /nurse  (nurse queue)
The API contract is in SPEC.md. CORS is open so a Base44 app can call it directly.
No authentication: demo only, synthetic data only.
"""

from __future__ import annotations

import io
import json
import os
import statistics
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import segno
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from . import asr, fixtures
from .config import ROOT, get_settings
from .erlang import spec_scenarios
from .questions import BY_ID, QUESTIONS, public_questions
from .sessions import NotFound, SessionError, get_store

WEB = ROOT / "web"
BENCH_FILE = ROOT / "benchmarks" / "latest.json"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
AUDIO_EXT = {
    "audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "video/mp4": "m4a",
    "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav",
}


def _mode() -> str:
    return os.getenv("TRIAGE_MODE", "auto")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load Whisper in the background so the first voice note is not slow.
    if not os.getenv("TRIAGE_SKIP_WARMUP") and asr.is_model_cached():
        threading.Thread(target=lambda: asr._load(get_settings().whisper_model), daemon=True).start()
    yield


app = FastAPI(title="Ambient ER intake", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFound):
        return HTTPException(404, detail={"error": "not_found", "message": str(exc)})
    return HTTPException(400, detail={"error": "bad_request", "message": str(exc)})


def _ext(filename: str | None, content_type: str | None) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in AUDIO_EXT:
        return AUDIO_EXT[ctype]
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    return suffix if suffix in {"webm", "ogg", "m4a", "mp4", "aac", "mp3", "wav", "flac"} else "webm"


# ----------------------------------------------------------------------------- pages
def _page(name: str) -> FileResponse:
    return FileResponse(WEB / name, media_type="text/html", headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def judge_page():
    target = "judge.html" if (WEB / "judge.html").exists() else "index.html"
    return _page(target)


@app.get("/p", include_in_schema=False)
def patient_page():
    return _page("patient.html")


@app.get("/nurse", include_in_schema=False)
def nurse_page():
    return _page("nurse.html")


@app.get("/app", include_in_schema=False)
@app.get("/react", include_in_schema=False)
def react_app():
    dist_index = WEB / "dist" / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index, media_type="text/html", headers={"Cache-Control": "no-store"})
    return _page("patient.html")


DIST_ASSETS = WEB / "dist" / "assets"
if DIST_ASSETS.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=DIST_ASSETS), name="assets")


# ----------------------------------------------------------------------------- Base44 helpers
@app.post("/api/intake")
async def api_intake(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    # Return a case the nurse workstation can render: merge the submitted
    # patient data (chart, suggestedTier, redFlags, summaries) with the
    # queue-level fields the frontend expects at the top level.
    return {
        **body,
        "id": f"case-{int(time.time()*1000)}",
        "status": "waiting",
        "label": "NEW",
        "waitingMinutes": 0,
        "patient": body.get("patient") or {"age": None, "sex": ""},
        "probabilities": body.get("probabilities") or [
            {"esi": 1, "probability": 0.1, "expectedLoss": 1.0},
            {"esi": 2, "probability": 0.2, "expectedLoss": 2.0},
            {"esi": 3, "probability": 0.4, "expectedLoss": 4.0},
            {"esi": 4, "probability": 0.2, "expectedLoss": 2.0},
            {"esi": 5, "probability": 0.1, "expectedLoss": 1.0},
        ],
        "audioNoteIds": [],
        "confirmedESI": None,
        "confirmedAt": None,
        "reviewSeconds": None,
        "created_at": time.time(),
    }


@app.post("/api/confirm-esi")
async def api_confirm_esi(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    return {"ok": True, "status": "confirmed", **body}


# ----------------------------------------------------------------------------- general
@app.get("/api/health")
def health():
    s = get_settings()
    live_g, live_j = s.gemini_live_ready, s.jev_live_ready
    return {
        "ok": True,
        "mode": "live" if live_g and live_j else ("partly live" if live_g or live_j else "offline"),
        "keys": {"gemini": bool(s.google_api_key), "jev": bool(s.typesafe_api_key)},
        "models": {"gemini": s.gemini_model, "jev": s.jev_model, "whisper": s.whisper_model},
        "speech_model_ready": asr.is_model_cached(),
        "run_mode": _mode(),
        "repo_url": os.getenv("REPO_URL", ""),
    }


@app.get("/api/questions")
def questions():
    return {"questions": public_questions()}


@app.get("/api/qr.svg", include_in_schema=False)
def qr(request: Request, path: str = "/p"):
    base = os.getenv("PUBLIC_URL", "").rstrip("/")
    if not base:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
        base = f"{proto}://{host}"
    buf = io.BytesIO()
    segno.make(base + (path if path.startswith("/") else "/" + path), error="m").save(
        buf, kind="svg", scale=6, border=2, dark="#111111")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


# ----------------------------------------------------------------------------- patient
@app.post("/api/sessions")
def create_session():
    store = get_store()
    s = store.create()
    return {**store.public(s), "questions": public_questions()}


@app.get("/api/sessions/{sid}/state")
def session_state(sid: str):
    store = get_store()
    try:
        return store.public(store.get(sid))
    except SessionError as exc:
        raise _http(exc) from exc


def _voice_answer(sid: str, qid: str, data: bytes, ext: str) -> dict:
    store = get_store()
    if qid not in BY_ID:
        raise HTTPException(400, detail={"error": "bad_request", "message": f"unknown question {qid!r}"})
    if not data:
        raise HTTPException(400, detail={"error": "empty_audio", "message": "the recording is empty"})
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, detail={"error": "too_large", "message": "recordings are limited to 25 MB"})
    if not asr.is_model_cached():
        raise HTTPException(503, detail={"error": "speech_model_missing",
                                         "message": "run: uv run python -m triage.cli prefetch"})
    path = store.answer_dir(sid) / f"{qid}_{int(time.time() * 1000)}.{ext}"
    path.write_bytes(data)
    try:
        out = asr.transcribe(path)
    except Exception as exc:  # undecodable audio
        raise HTTPException(422, detail={"error": "unreadable_audio", "message": type(exc).__name__}) from exc
    if not out.text.strip():
        raise HTTPException(422, detail={"error": "no_speech", "message": "no words were heard"})
    try:
        s = store.add_answer(sid, qid, out.text, "voice", audio_file=path.name, asr_ms=out.latency_ms)
    except SessionError as exc:
        raise _http(exc) from exc
    return {"answer": {"question_id": qid, "source": "voice", "asr_ms": out.latency_ms}, **store.public(s)}


def _download(url: str) -> tuple[bytes, str]:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise HTTPException(400, detail={"error": "audio_url", "message": f"download failed ({resp.status_code})"})
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise HTTPException(413, detail={"error": "too_large", "message": "recordings are limited to 25 MB"})
                chunks.append(chunk)
            return b"".join(chunks), _ext(url.split("?")[0], resp.headers.get("content-type"))


@app.post("/api/sessions/{sid}/answers")
async def add_answer(sid: str, request: Request):
    """multipart: question_id + (audio file | text)   or   JSON: {question_id, text | audio_url}."""
    store = get_store()
    try:
        store.get(sid)
    except SessionError as exc:
        raise _http(exc) from exc
    ctype = request.headers.get("content-type", "")
    if ctype.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        form = await request.form()
        qid, text = str(form.get("question_id") or ""), str(form.get("text") or "")
        upload = form.get("audio")
        if upload is not None and hasattr(upload, "read"):
            data = await upload.read()
            return await run_in_threadpool(_voice_answer, sid, qid, data, _ext(upload.filename, upload.content_type))
    else:
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(400, detail={"error": "bad_request", "message": "send JSON or multipart"}) from exc
        qid, text, url = str(body.get("question_id") or ""), str(body.get("text") or ""), body.get("audio_url")
        if url:
            data, ext = await run_in_threadpool(_download, str(url))
            return await run_in_threadpool(_voice_answer, sid, qid, data, ext)
    try:
        s = store.add_answer(sid, qid, text, "text")
    except SessionError as exc:
        raise _http(exc) from exc
    return {"answer": {"question_id": qid, "source": "text"}, **store.public(s)}


@app.post("/api/sessions/{sid}/submit")
async def submit(sid: str):
    store = get_store()
    try:
        s = await run_in_threadpool(store.submit, sid, _mode())
    except SessionError as exc:
        raise _http(exc) from exc
    return {"id": sid, "status": s["status"]}


# ----------------------------------------------------------------------------- nurse
@app.get("/api/queue")
def queue():
    return {"patients": get_store().queue(), "now": time.time()}


@app.get("/api/sessions/{sid}")
def session_detail(sid: str):
    store = get_store()
    try:
        return store.detail(store.get(sid))
    except SessionError as exc:
        raise _http(exc) from exc


@app.post("/api/sessions/{sid}/open")
def open_session(sid: str):
    store = get_store()
    try:
        return store.detail(store.open(sid))
    except SessionError as exc:
        raise _http(exc) from exc


@app.post("/api/sessions/{sid}/confirm")
async def confirm(sid: str, request: Request):
    store = get_store()
    try:
        body = await request.json()
        esi = int(body.get("official_esi"))
        rb = body.get("readback_seconds")
        s = await run_in_threadpool(store.confirm, sid, esi, body.get("fields") or {}, None if rb is None else float(rb))
        return store.detail(s)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, detail={"error": "bad_request", "message": "official_esi must be 1 to 5"}) from exc
    except SessionError as exc:
        raise _http(exc) from exc


@app.get("/api/sessions/{sid}/audio/{name}", include_in_schema=False)
def session_audio(sid: str, name: str):
    """The patient's own voice note, for the nurse to replay. Only files listed in that session's answers."""
    store = get_store()
    try:
        s = store.get(sid)
    except SessionError as exc:
        raise _http(exc) from exc
    if name not in {a.get("audio_file") for a in s["answers"]}:
        raise HTTPException(404, detail={"error": "not_found", "message": "no such recording"})
    path = store.answer_dir(sid) / name
    if not path.is_file():
        raise HTTPException(404, detail={"error": "not_found", "message": "no such recording"})
    return FileResponse(path)


@app.get("/api/sessions/{sid}/pdf")
def session_pdf(sid: str, kind: str = "intake"):
    store = get_store()
    try:
        path = store.pdf_path(sid, kind)
    except SessionError as exc:
        raise _http(exc) from exc
    return FileResponse(path, media_type="application/pdf", filename=path.name)


# ----------------------------------------------------------------------------- judges
@app.post("/api/demo/{fixture_id}")
async def demo(fixture_id: str, voice: bool = False):
    """Run a stored sample case end to end (it appears in the nurse queue). voice=true transcribes its audio clip."""
    if fixture_id not in fixtures.FIXTURE_IDS:
        raise HTTPException(404, detail={"error": "not_found", "message": f"no sample {fixture_id!r}"})
    store = get_store()
    s = store.create(fixture_id)
    clip = fixtures.audio_path(fixture_id)
    if voice and clip is not None:
        await run_in_threadpool(_voice_answer, s["id"], "q1", clip.read_bytes(), clip.suffix.lstrip("."))
    else:
        store.add_answer(s["id"], "q1", fixtures.load_transcript(fixture_id), "text")
    s = await run_in_threadpool(store.submit, s["id"], _mode())
    return store.detail(s)


@app.get("/api/fixtures/{fixture_id}/audio", include_in_schema=False)
def fixture_audio(fixture_id: str):
    if fixture_id not in fixtures.FIXTURE_IDS or fixtures.audio_path(fixture_id) is None:
        raise HTTPException(404, detail={"error": "not_found", "message": "no clip"})
    return FileResponse(fixtures.audio_path(fixture_id), media_type="audio/wav")


@app.get("/api/benchmarks")
def benchmarks():
    s = get_settings()
    sc = spec_scenarios()
    # Per intake: the pipeline after the last answer PLUS the speech-to-text already spent on each voice note.
    totals = [
        x["result"]["latency_ms"]["total"] + sum(a.get("asr_ms") or 0 for a in x["answers"] if a.get("source") == "voice")
        for x in get_store().all()
        if x.get("result") and "total" in x["result"].get("latency_ms", {})
    ]
    snapshot = json.loads(BENCH_FILE.read_text(encoding="utf-8")) if BENCH_FILE.exists() else None
    return {
        "snapshot": snapshot,
        "live": {
            "mode": health()["mode"],
            "questions": len(QUESTIONS),
            "loss": {"c_under": s.c_under, "c_over": s.c_over,
                     "escalation_line_esi4_vs_esi2": round(s.c_over / (s.c_over + s.c_under), 4)},
            "erlang": {"manual_wait_min": round(sc["manual"].wait_minutes, 1),
                       "automated_wait_s": round(sc["automated"].wait_seconds, 1),
                       "reduction_pct": round(sc["wait_reduction"] * 100, 1) if sc["wait_reduction"] else None},
            "runs_this_server": len(totals),
            "median_run_ms": round(statistics.median(totals), 1) if totals else None,
        },
    }
