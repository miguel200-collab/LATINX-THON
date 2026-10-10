"""Spanish read-back script: fixed templates, no model, patient's own words for free text."""

from triage import fixtures as fx
from triage.readback import readback_es
from triage.schemas import ExtractionResult


def test_chest_pain_read_back():
    lines = readback_es(fx.load_chart("A"))
    assert lines[0] == "Usted siente un apretón o presión en el pecho."
    assert "Empezó de repente, hace unas 2 horas." in lines
    assert "Se le corre al brazo izquierdo y a la mandíbula." in lines
    assert "Del 1 al 10, es un 9." in lines
    assert "Usted dijo: «Estaba sentada, no hice esfuerzo»." in lines
    assert "También tiene falta de aire y sudor frío." in lines
    assert lines[-1] == "¿Es correcto?"


def test_ankle_read_back_with_unknown_quality_and_no_radiation():
    lines = readback_es(fx.load_chart("B"))
    assert lines[0] == "Usted tiene una molestia en el tobillo o el pie."
    assert "Empezó de repente, hace un día." in lines
    assert "No se le corre a otra parte." in lines
    assert "Del 1 al 10, es un 5." in lines
    assert not any(line.startswith("También tiene") for line in lines)


def test_empty_chart_only_asks_for_confirmation():
    assert readback_es(ExtractionResult()) == ["¿Es correcto?"]
