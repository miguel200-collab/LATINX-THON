"""The fixtures are the offline path and the test set, so they have to be correct themselves."""

import json

import pytest

from triage import fixtures as fx
from triage.checks import check_gold, fields_without_quote, verify_quotes
from triage.loss import calculate_safest_esi


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_stored_chart_matches_gold(fid):
    assert check_gold(fx.load_chart(fid), fx.load_gold(fid)) == []


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_every_quote_is_really_in_the_transcript(fid):
    assert verify_quotes(fx.load_chart(fid), fx.load_transcript(fid)) == []


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_every_filled_field_has_a_quote(fid):
    assert fields_without_quote(fx.load_chart(fid)) == []


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_transcripts_match_themselves_and_have_audio(fid):
    assert fx.match_fixture(fx.load_transcript(fid)) == fid
    assert fx.audio_path(fid) is not None, "run ./scripts/make_synthetic_audio.sh"


def test_fixture_probabilities_are_distributions_with_expected_flags():
    expected = {"A": 2, "A_long": 2, "B": 4, "C": 2}  # suggested review tier from the spec's worked examples
    for fid, tier in expected.items():
        probs = fx.load_probabilities(fid)
        assert sum(probs) == pytest.approx(1.0)
        assert calculate_safest_esi(probs)["optimal_safety_tier"] == tier


def test_jev_state_hides_generated_text_and_quotes():
    state = fx.load_chart("A").jev_state()
    assert set(state) == {"symptoms"}
    text = json.dumps(state)
    assert "raw_summary_en" not in text and "source_phrases" not in text
    assert "apretón" not in text  # Spanish quotes are not sent to Jev
    assert state["symptoms"]["location"] == "chest"


def test_tampered_quote_is_flagged():
    chart = fx.load_chart("A")
    chart.source_phrases.quality = "sentí un dolor punzante"  # not in the transcript
    assert verify_quotes(chart, fx.load_transcript("A")) == ["quality"]


def test_small_speech_to_text_spelling_slips_are_tolerated():
    """Whisper wrote 'pal' for "pa'l" and 'sudor frío' for 'sudo frío' in the demo clip. That is not a made-up quote."""
    heard = fx.load_transcript("A").replace("pa'l", "pal").replace("sudo frío", "sudor frío")
    assert verify_quotes(fx.load_chart("A"), heard) == []


def test_digits_written_by_speech_to_text_match_the_spoken_numbers():
    """Whisper wrote '9 de 10' for 'nueve de diez' in the long clip."""
    heard = fx.load_transcript("A_long").replace("nueve de diez", "9 de 10").replace("las diez", "las 10")
    assert verify_quotes(fx.load_chart("A_long"), heard) == []


def test_a_misheard_key_phrase_is_still_flagged():
    """'desde que cené me arde' heard as 'desde que se enemear de' loses the symptom words: the nurse must see that."""
    heard = fx.load_transcript("C").replace("desde que cené me arde", "desde que se enemear de")
    flagged = verify_quotes(fx.load_chart("C"), heard)
    assert "quality" in flagged and "onset" in flagged


def test_a_fabricated_quote_is_flagged_but_a_real_one_is_not():
    chart = fx.load_chart("B")
    chart.source_phrases.red_flag_symptoms = "me desmayé en la cocina y vomité sangre"   # never said
    assert verify_quotes(chart, fx.load_transcript("B")) == ["red_flag_symptoms"]
    chart.source_phrases.red_flag_symptoms = "no me pegué en la cabeza"                   # really said
    assert verify_quotes(chart, fx.load_transcript("B")) == []


def test_gold_check_catches_a_wrong_chart():
    chart = fx.load_chart("B")
    chart.severity_1_to_10 = 8
    chart.red_flag_symptoms = ["chest_pain"]
    failures = check_gold(chart, fx.load_gold("B"))
    assert any("severity" in f for f in failures)
    assert any("red_flag_symptoms" in f for f in failures)


def test_gold_check_catches_social_talk_leaking_into_the_chart():
    chart = fx.load_chart("A_long")
    chart.raw_summary_en += " The grandson visited from Orlando."
    assert any("social talk" in f for f in check_gold(chart, fx.load_gold("A_long")))


def test_unknown_fixture_id_is_rejected():
    with pytest.raises(KeyError):
        fx.load_transcript("Z")
