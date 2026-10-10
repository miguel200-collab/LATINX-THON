"""Which questions turn green. Deterministic; no AI; nothing is said back to the patient."""

from triage import fixtures as fx
from triage.coverage import compute_state


def q1(text):
    return [{"question_id": "q1", "text": text}]


def statuses(state):
    return {qid: v["status"] for qid, v in state["questions"].items()}


def test_nothing_answered_starts_at_question_one():
    st = compute_state([])
    assert st["next"] == "q1" and not st["done"]
    assert set(statuses(st).values()) == {"pending"}


def test_rich_chest_pain_story_covers_four_questions_but_never_the_red_flag_question():
    st = compute_state(q1(fx.load_transcript("A")))
    s = statuses(st)
    assert s["q1"] == "answered"
    assert s["q2"] == s["q3"] == s["q4"] == s["q5"] == "covered"
    assert s["q6"] == "pending" and st["next"] == "q6"          # red flags are always asked directly


def test_ankle_story_still_asks_what_the_pain_feels_like():
    st = compute_state(q1(fx.load_transcript("B")))
    s = statuses(st)
    assert s["q2"] == "covered"          # tobillo + "no me duele nada más"
    assert s["q3"] == "covered"          # "me torcí" + "hace un día"
    assert s["q4"] == "partial"          # a 1-10 number but no description of the pain
    assert st["questions"]["q4"]["parts"] == {"quality": False, "severity": True}
    assert s["q5"] == "covered"          # "cuando lo apoyo"
    assert st["next"] == "q4"


def test_epigastric_story_asks_what_makes_it_worse():
    st = compute_state(q1(fx.load_transcript("C")))
    s = statuses(st)
    assert s["q2"] == s["q3"] == s["q4"] == "covered"
    assert s["q5"] == "pending" and st["next"] == "q5"


def test_known_false_positives_do_not_skip_questions():
    st = compute_state(q1("Me duele como un cinco de diez."))
    assert st["questions"]["q4"]["parts"]["quality"] is False      # "como un ..." is not a description
    st = compute_state(q1("Empezó a las diez de la mañana."))
    assert st["questions"]["q4"]["parts"]["severity"] is False     # a time, not a score
    assert st["questions"]["q3"]["parts"]["duration"] is True
    st = compute_state(q1("Tengo una molestia en el pecho."))
    assert st["questions"]["q4"]["parts"]["quality"] is False


def test_mentioning_one_red_flag_does_not_skip_the_red_flag_question():
    st = compute_state(q1("Me falta el aire y sudo frío."))
    assert st["questions"]["q6"]["status"] == "pending"


def test_a_direct_answer_turns_green_even_if_it_is_vague():
    st = compute_state(q1("Me siento mal.") + [{"question_id": "q4", "text": "Pues no sé."}])
    assert st["questions"]["q4"]["status"] == "answered" and st["questions"]["q4"]["green"]


def test_blank_answers_do_not_count():
    st = compute_state([{"question_id": "q1", "text": "   "}])
    assert st["questions"]["q1"]["status"] == "pending"


def test_done_when_every_question_is_green():
    answers = q1(fx.load_transcript("A")) + [{"question_id": "q6", "text": "No, nada de eso."}]
    st = compute_state(answers)
    assert st["done"] and st["next"] is None
