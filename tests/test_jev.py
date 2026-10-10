"""Jev scoring with a faked call and with the real SDK classes. No network, no keys."""

import pytest

from triage import fixtures as fx
from triage import jev
from triage.loss import calculate_safest_esi
from triage.util import ApiTimeout


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-test-key-456")


def fake_answer(vector, confidence=0.72, model="jev-1.13.0", scramble=True):
    probs = {f"esi_{i + 1}": p for i, p in enumerate(vector)}
    if scramble:  # the real API does not promise declared order
        probs = dict(reversed(list(probs.items())))
    return {"choice": f"esi_{vector.index(max(vector)) + 1}", "confidence": confidence,
            "probabilities": probs, "model": model}


# --- by-key vector -------------------------------------------------------------

def test_probability_vector_is_built_by_key_not_position():
    scrambled = {"esi_5": 0.05, "esi_3": 0.6, "esi_1": 0.02, "esi_4": 0.15, "esi_2": 0.18}
    assert jev.probability_vector(scrambled) == [0.02, 0.18, 0.6, 0.15, 0.05]


def test_missing_option_is_an_error():
    with pytest.raises(jev.JevError):
        jev.probability_vector({"esi_1": 0.5, "esi_2": 0.5})


def test_all_zero_is_an_error():
    with pytest.raises(jev.JevError):
        jev.probability_vector({f"esi_{i}": 0.0 for i in range(1, 6)})


# --- the question ---------------------------------------------------------------

def test_question_option_order_can_be_reversed():
    fwd = list(jev.build_question("forward").criteria)
    rev = list(jev.build_question("reversed").criteria)
    assert fwd == ["esi_1", "esi_2", "esi_3", "esi_4", "esi_5"]
    assert rev == list(reversed(fwd))
    with pytest.raises(ValueError):
        jev.build_question("sideways")


def test_question_text_is_literal_and_names_the_state():
    q = jev.build_question()
    assert "`symptoms`" in q.instructions
    assert "life-saving" in q.criteria["esi_1"]


# --- live path with a faked call --------------------------------------------------

def test_live_success_reads_probabilities_confidence_and_model(live, monkeypatch):
    seen = {}

    def fake(state, settings, order="forward"):
        seen["state"], seen["order"] = state, order
        return fake_answer([0.02, 0.18, 0.60, 0.15, 0.05])

    monkeypatch.setattr(jev, "_jev_call", fake)
    out = jev.score(fx.load_chart("A"), fixture_id="A")
    assert out.source == "jev"
    assert out.probabilities == [0.02, 0.18, 0.6, 0.15, 0.05]
    assert out.confidence == pytest.approx(0.72)
    assert out.model == "jev-1.13.0"
    assert out.prompt_version == "RP-J1 v1"
    assert set(seen["state"]) == {"symptoms"}            # Jev sees the structured fields only
    assert "raw_summary_en" not in str(seen["state"])
    assert seen["order"] == "forward"


def test_live_probabilities_feed_the_loss_gate(live, monkeypatch):
    monkeypatch.setattr(jev, "_jev_call", lambda s, st, o="forward": fake_answer([0.02, 0.18, 0.60, 0.15, 0.05]))
    out = jev.score(fx.load_chart("A"))
    decision = calculate_safest_esi(out.probabilities)
    assert (decision["raw_argmax_tier"], decision["optimal_safety_tier"]) == (3, 2)


def test_reversed_order_is_passed_through(live, monkeypatch):
    orders = []
    monkeypatch.setattr(jev, "_jev_call", lambda s, st, o="forward": (orders.append(o), fake_answer([0, 0, 0, 1, 0]))[1])
    out = jev.score(fx.load_chart("B"), order="reversed")
    assert orders == ["reversed"] and out.option_order == "reversed"


def test_timeout_falls_back_to_fixture_vector_when_known(live, monkeypatch):
    def slow(state, settings, order="forward"):
        raise ApiTimeout("no response within 5.0s")

    monkeypatch.setattr(jev, "_jev_call", slow)
    out = jev.score(fx.load_chart("C"), fixture_id="C")
    assert out.source == "fixture_probs"
    assert out.probabilities == [0.0, 0.2, 0.0, 0.8, 0.0]
    assert "no response" in out.note


def test_failure_without_fixture_gives_the_safety_hold(live, monkeypatch):
    monkeypatch.setattr(jev, "_jev_call", lambda s, st, o="forward": (_ for _ in ()).throw(RuntimeError("boom")))
    out = jev.score(fx.load_chart("C"))
    assert out.source == "regex_hold" and out.probabilities is None


def test_api_key_is_never_leaked_into_the_note(live, monkeypatch):
    def boom(state, settings, order="forward"):
        raise RuntimeError("401 bad key ts-test-key-456")

    monkeypatch.setattr(jev, "_jev_call", boom)
    out = jev.score(fx.load_chart("B"), fixture_id="B")
    assert "ts-test-key-456" not in out.note and "***" in out.note


# --- modes ---------------------------------------------------------------------------

def test_no_key_uses_fixture_vector():
    out = jev.score(fx.load_chart("B"), fixture_id="B")
    assert out.source == "fixture_probs"
    assert out.probabilities == [0.0, 0.05, 0.0, 0.95, 0.0]
    assert "TYPESAFE_API_KEY" in out.note


def test_no_key_and_unknown_case_gives_the_hold():
    out = jev.score(fx.load_chart("B"))
    assert out.source == "regex_hold" and out.probabilities is None


def test_offline_mode_never_calls_the_api(live, monkeypatch):
    def forbidden(state, settings, order="forward"):
        raise AssertionError("API must not be called in offline mode")

    monkeypatch.setattr(jev, "_jev_call", forbidden)
    assert jev.score(fx.load_chart("A"), fixture_id="A", mode="offline").source == "fixture_probs"


def test_outage_mode_is_always_the_hold(live):
    out = jev.score(fx.load_chart("A"), fixture_id="A", mode="outage")
    assert out.source == "regex_hold" and out.probabilities is None


def test_score_live_refuses_without_a_key():
    with pytest.raises(jev.JevError):
        jev.score_live(fx.load_chart("A"))


# --- real SDK classes, HTTP call replaced ----------------------------------------------

def test_real_sdk_request_and_response_shapes(live, monkeypatch):
    import typesafe_sdk as ts

    captured = {}
    response = ts.SystemOneResponse.model_validate({
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 120, "output_tokens": 30},
        "answers": {
            "presentation_acuity": {
                "type": "choice",
                "choice": "esi_3",
                "confidence": 0.64,
                # deliberately out of declared order, like the vendor's own sample
                "probabilities": {"esi_3": 0.6, "esi_5": 0.05, "esi_1": 0.02, "esi_4": 0.15, "esi_2": 0.18},
            }
        },
    })

    def fake_system_one(self, state, questions, **kwargs):
        captured.update(state=state, questions=questions)
        return response

    monkeypatch.setattr(ts.TypeSafeClient, "system_one", fake_system_one)
    out = jev.score(fx.load_chart("A"), fixture_id="A")

    assert out.source == "jev"
    assert out.probabilities == [0.02, 0.18, 0.6, 0.15, 0.05]
    assert out.choice == "esi_3" and out.model == "jev-1.13.0"
    assert out.confidence == pytest.approx(0.64)
    assert list(captured["questions"]) == ["presentation_acuity"]
    assert captured["state"]["symptoms"]["location"] == "chest"


# --- sanity-check runner ---------------------------------------------------------------------

def _plausible(chart_state):
    sym = chart_state["symptoms"]
    if "chest_pain" in sym["red_flag_symptoms"]:
        return [0.05, 0.55, 0.30, 0.08, 0.02]
    return [0.00, 0.03, 0.12, 0.70, 0.15]


def test_sanity_runner_passes_for_a_sensible_model(live, monkeypatch):
    monkeypatch.setattr(jev, "_jev_call", lambda state, s, order="forward": fake_answer(_plausible(state)))
    result = jev.run_sanity(("A", "B", "C"), repeats=2)
    assert all(c["passed"] for c in result["checks"]), result["checks"]
    assert result["models"] == ["jev-1.13.0"]


def test_sanity_runner_catches_option_order_bias(live, monkeypatch):
    def biased(state, settings, order="forward"):
        vector = _plausible(state)
        if order == "reversed":  # model leans to whichever option is listed first
            vector = [0.70, 0.20, 0.05, 0.03, 0.02]
        return fake_answer(vector)

    monkeypatch.setattr(jev, "_jev_call", biased)
    result = jev.run_sanity(("A", "B"), repeats=1)
    flip = [c for c in result["checks"] if c["name"].startswith("3.")][0]
    assert flip["passed"] is False


def test_sanity_runner_catches_a_model_that_cannot_tell_cases_apart(live, monkeypatch):
    monkeypatch.setattr(jev, "_jev_call", lambda state, s, order="forward": fake_answer([0.1, 0.1, 0.6, 0.1, 0.1]))
    result = jev.run_sanity(("A", "B"), repeats=1)
    assert not result["checks"][0]["passed"]


def test_gemini_acuity_fallback_when_jev_unready(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setattr(
        jev,
        "_gemini_acuity_call",
        lambda state, s, order="forward": {
            "choice": "esi_4",
            "confidence": 0.85,
            "probabilities": {"esi_1": 0.0, "esi_2": 0.05, "esi_3": 0.1, "esi_4": 0.8, "esi_5": 0.05},
            "model": "gemini-3.8-flash",
        },
    )
    chart = fx.load_chart("B")
    out = jev.score(chart)
    assert out.source == "gemini_acuity"
    assert out.probabilities == [0.0, 0.05, 0.1, 0.8, 0.05]
    assert out.choice == "esi_4"
    assert out.confidence == 0.85
    assert out.model == "gemini-3.8-flash"


def test_gemini_acuity_fallback_when_jev_fails(live, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setattr(jev, "_jev_call", lambda s, st, o="forward": (_ for _ in ()).throw(RuntimeError("401 Unauthorized")))
    monkeypatch.setattr(
        jev,
        "_gemini_acuity_call",
        lambda state, s, order="forward": {
            "choice": "esi_2",
            "confidence": 0.9,
            "probabilities": {"esi_1": 0.05, "esi_2": 0.9, "esi_3": 0.05, "esi_4": 0.0, "esi_5": 0.0},
            "model": "gemini-3.8-flash",
        },
    )
    chart = fx.load_chart("A")
    out = jev.score(chart)
    assert out.source == "gemini_acuity"
    assert out.probabilities == [0.05, 0.9, 0.05, 0.0, 0.0]
    assert "Jev call failed" in out.note

