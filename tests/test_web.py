"""The three pages are served, and the patient page never shows a triage level."""

from fastapi.testclient import TestClient

from triage import api
from triage.config import ROOT


def test_pages_are_served():
    client = TestClient(api.app)
    for path, marker in (("/", "Ambient ER intake"), ("/p", "Sala de Emergencias"), ("/nurse", "Triage queue")):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
        assert marker in r.text


def test_patient_page_never_mentions_a_triage_level_or_ai_reply():
    html = (ROOT / "web" / "patient.html").read_text(encoding="utf-8")
    assert "ESI" not in html and "tier" not in html.lower()
    assert "Mantenga presionado" in html and "Deslice" in html          # hold to record, slide to lock/cancel
    assert "/api/sessions" in html and "/submit" in html


def test_nurse_page_has_the_official_esi_and_both_pdfs():
    html = (ROOT / "web" / "nurse.html").read_text(encoding="utf-8")
    for needle in ("Official ESI", "pdf?kind=confirmed", "/confirm", "Read this back to the patient", "STORED EXAMPLE"):
        assert needle in html


def test_judge_page_shows_both_sides():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'src="/p?new=1"' in html and 'src="/nurse?embed=1"' in html and 'allow="microphone' in html
    assert "/api/benchmarks" in html and "/api/demo/" in html
