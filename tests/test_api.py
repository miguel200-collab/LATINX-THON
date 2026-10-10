"""The web API end to end, with no network and no keys (Whisper is faked except in the one slow test)."""

import re

import pypdf
import pytest
from fastapi.testclient import TestClient

from triage import api, asr
from triage import fixtures as fx
from triage.sessions import SessionStore, get_store


@pytest.fixture
def client():
    return TestClient(api.app)


def fake_asr(text="Me duele mucho el pecho desde hace una hora.", ms=900.0):
    return lambda path, **kw: asr.AsrOutcome(text=text, latency_ms=ms, load_ms=0.0, model="whisper small",
                                            audio_seconds=4.0, language="es", language_probability=1.0)


def pdf_text(path):
    reader = pypdf.PdfReader(str(path))
    return len(reader.pages), re.sub(r"\s+", " ", " ".join(p.extract_text() for p in reader.pages))


def new_session(client):
    r = client.post("/api/sessions")
    assert r.status_code == 200
    return r.json()


# --- basics ----------------------------------------------------------------------------------------

def test_health_and_questions(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["mode"] == "offline" and h["keys"] == {"gemini": False, "jev": False}
    qs = client.get("/api/questions").json()["questions"]
    assert [q["id"] for q in qs] == ["q1", "q2", "q3", "q4", "q5", "q6"]
    assert qs[0]["es"] == "Cuéntenos qué le pasa hoy." and qs[5]["auto_cover"] is False


def test_cors_is_open_for_a_base44_app(client):
    r = client.get("/api/questions", headers={"Origin": "https://my-app.base44.app"})
    assert r.headers.get("access-control-allow-origin") == "*"


# --- the patient side ----------------------------------------------------------------------------

def test_patient_flow_turns_questions_green_and_never_reveals_the_tier(client):
    s = new_session(client)
    assert s["state"]["next"] == "q1" and len(s["questions"]) == 6
    r = client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q1", "text": fx.load_transcript("A")})
    body = r.json()
    assert r.status_code == 200
    green = {q for q, v in body["state"]["questions"].items() if v["green"]}
    assert green == {"q1", "q2", "q3", "q4", "q5"} and body["state"]["next"] == "q6"
    for secret in ("result", "flag", "suggested_review_tier", "chart", "text"):
        assert secret not in body and secret not in body["answer"]
    r = client.post(f"/api/sessions/{s['id']}/answers", data={"question_id": "q6", "text": "No, nada de eso."})
    assert r.json()["state"]["done"] is True
    r = client.post(f"/api/sessions/{s['id']}/submit")
    assert r.json() == {"id": s["id"], "status": "waiting"}


def test_answer_errors(client):
    s = new_session(client)
    assert client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q9", "text": "hola"}).status_code == 400
    assert client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q1", "text": "   "}).status_code == 400
    assert client.post("/api/sessions/nope00/answers", json={"question_id": "q1", "text": "hola"}).status_code == 404
    assert client.post(f"/api/sessions/{s['id']}/submit").status_code == 400      # nothing answered yet


def test_no_answers_after_sending(client):
    s = new_session(client)
    client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q1", "text": "Me duele la cabeza."})
    client.post(f"/api/sessions/{s['id']}/submit")
    assert client.post(f"/api/sessions/{s['id']}/submit").json()["status"] == "waiting"   # idempotent
    r = client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q2", "text": "En la frente."})
    assert r.status_code == 400


def test_voice_note_upload_is_transcribed(client, monkeypatch):
    monkeypatch.setattr(asr, "transcribe", fake_asr())
    monkeypatch.setattr(asr, "is_model_cached", lambda *a: True)
    s = new_session(client)
    r = client.post(f"/api/sessions/{s['id']}/answers", data={"question_id": "q1"},
                    files={"audio": ("nota.webm", b"fake-webm-bytes", "audio/webm;codecs=opus")})
    assert r.status_code == 200 and r.json()["answer"] == {"question_id": "q1", "source": "voice", "asr_ms": 900.0}
    saved = list(get_store().answer_dir(s["id"]).glob("q1_*.webm"))
    assert len(saved) == 1 and saved[0].read_bytes() == b"fake-webm-bytes"


def test_silent_voice_note_asks_for_a_retry(client, monkeypatch):
    monkeypatch.setattr(asr, "transcribe", fake_asr(text="  "))
    monkeypatch.setattr(asr, "is_model_cached", lambda *a: True)
    s = new_session(client)
    r = client.post(f"/api/sessions/{s['id']}/answers", data={"question_id": "q1"},
                    files={"audio": ("nota.webm", b"x", "audio/webm")})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "no_speech"


def test_missing_speech_model_is_a_clear_503(client, monkeypatch):
    monkeypatch.setattr(asr, "is_model_cached", lambda *a: False)
    s = new_session(client)
    r = client.post(f"/api/sessions/{s['id']}/answers", data={"question_id": "q1"},
                    files={"audio": ("nota.webm", b"x", "audio/webm")})
    assert r.status_code == 503 and "prefetch" in r.json()["detail"]["message"]


def test_audio_url_answers_for_base44(client, monkeypatch):
    monkeypatch.setattr(asr, "transcribe", fake_asr())
    monkeypatch.setattr(asr, "is_model_cached", lambda *a: True)
    monkeypatch.setattr(api, "_download", lambda url: (b"audio-bytes", "mp3"))
    s = new_session(client)
    r = client.post(f"/api/sessions/{s['id']}/answers",
                    json={"question_id": "q1", "audio_url": "https://files.base44.app/x.mp3"})
    assert r.status_code == 200 and r.json()["answer"]["source"] == "voice"


# --- the nurse side ------------------------------------------------------------------------------

def _sent_session(client, text="Me duele el pecho y me falta el aire."):
    s = new_session(client)
    client.post(f"/api/sessions/{s['id']}/answers", json={"question_id": "q1", "text": text})
    client.post(f"/api/sessions/{s['id']}/submit")
    return s["id"]


def test_nurse_queue_detail_confirm_and_both_pdfs(client):
    sid = _sent_session(client)
    queue = client.get("/api/queue").json()["patients"]
    row = [p for p in queue if p["id"] == sid][0]
    assert row["status"] == "waiting" and row["suggested_review_tier"] == 2 and row["label_kind"] == "hold"
    assert "chest_pain" in row["red_flags"]

    detail = client.post(f"/api/sessions/{sid}/open").json()
    assert detail["status"] == "in_review" and detail["readback_es"][-1] == "¿Es correcto?"
    assert detail["result"]["official_esi"] is None

    intake = get_store().pdf_path(sid, "intake")
    pages, text = pdf_text(intake)
    assert pages == 1 and re.search(r"OFFICIAL ESI ASSIGNED BY RN:\s*_+", text)

    r = client.post(f"/api/sessions/{sid}/confirm", json={
        "official_esi": 2, "readback_seconds": 41.5,
        "fields": {"location": {"status": "ok"}, "severity_1_to_10": {"status": "corrected", "value": "8/10"}}})
    assert r.status_code == 200
    done = r.json()
    assert done["status"] == "confirmed" and done["confirmation"]["official_esi"] == 2
    assert done["summary"]["official_esi"] == 2
    pages, text = pdf_text(get_store().pdf_path(sid, "confirmed"))
    assert pages == 1
    assert "OFFICIAL ESI ASSIGNED BY RN: ESI 2" in text and "Corrected by RN: 8/10" in text and "read-back 41.5 s" in text
    assert client.get(f"/api/sessions/{sid}/pdf?kind=confirmed").headers["content-type"] == "application/pdf"
    assert client.get(f"/api/sessions/{sid}/pdf").status_code == 200


def test_confirm_validation(client):
    sid = _sent_session(client)
    bad = [
        {"official_esi": 7},
        {"official_esi": "x"},
        {"official_esi": 2, "fields": {"location": {"status": "corrected", "value": ""}}},
        {"official_esi": 2, "fields": {"blood_type": {"status": "ok"}}},
    ]
    for body in bad:
        assert client.post(f"/api/sessions/{sid}/confirm", json=body).status_code == 400, body
    unsent = new_session(client)["id"]
    assert client.post(f"/api/sessions/{unsent}/confirm", json={"official_esi": 3}).status_code == 400
    assert client.get(f"/api/sessions/{unsent}/pdf").status_code == 400


def test_queue_orders_waiting_patients_by_suggested_tier(client):
    b = client.post("/api/demo/B").json()
    a = client.post("/api/demo/A").json()
    ids = [p["id"] for p in client.get("/api/queue").json()["patients"]]
    assert ids.index(a["id"]) < ids.index(b["id"])           # ESI 2 before ESI 4


# --- judges ------------------------------------------------------------------------------------------

def test_sample_case_runs_end_to_end_and_is_labeled(client):
    d = client.post("/api/demo/A").json()
    assert d["status"] == "waiting" and d["fixture_id"] == "A"
    assert d["summary"]["suggested_review_tier"] == 2 and d["summary"]["raw_argmax_tier"] == 3
    assert d["result"]["labels"]["headline"] == "FIXTURE PROBABILITIES - NOT MODEL OUTPUT"
    assert client.post("/api/demo/Z").status_code == 404


def test_benchmarks_and_qr(client):
    live = client.get("/api/benchmarks").json()["live"]
    assert live["erlang"]["manual_wait_min"] == 25.7 and live["loss"]["escalation_line_esi4_vs_esi2"] == 0.0909
    r = client.get("/api/qr.svg?path=/p", headers={"x-forwarded-proto": "https", "x-forwarded-host": "demo.trycloudflare.com"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and b"<svg" in r.content


def test_fixture_audio_is_served_for_the_sample_voice(client):
    r = client.get("/api/fixtures/A/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and len(r.content) > 100_000


def test_sessions_survive_a_restart(client):
    sid = _sent_session(client)
    reloaded = SessionStore(get_store().root)
    assert reloaded.get(sid)["status"] == "waiting"


@pytest.mark.slow
@pytest.mark.skipif(not asr.is_model_cached("small"), reason="Whisper 'small' is not downloaded")
def test_sample_case_with_real_speech_to_text(client):
    d = client.post("/api/demo/A?voice=true").json()
    assert d["answers"][0]["source"] == "voice" and "apretón" in d["answers"][0]["text"].lower()
    assert d["summary"]["suggested_review_tier"] == 2
