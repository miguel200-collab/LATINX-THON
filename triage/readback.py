"""A Spanish read-back script built from the chart with fixed templates (no model).

A nurse who does not speak Spanish can read it to the patient and get a yes or no. Free-text
fields are never translated by a model: provocation is read back as the patient's own quote.
"""

from __future__ import annotations

from .schemas import ExtractionResult

LOCATION_ES = {
    "chest": "el pecho", "upper_abdomen": "la boca del estómago", "lower_abdomen": "la parte baja del estómago",
    "head": "la cabeza", "neck": "el cuello", "back": "la espalda", "shoulder_arm": "el hombro o el brazo",
    "hand": "la mano", "hip_leg": "la cadera o la pierna", "knee": "la rodilla", "ankle_foot": "el tobillo o el pie",
    "other": "otra parte del cuerpo",
}
QUALITY_ES = {
    "crushing_pressure": "un apretón o presión", "sharp": "un dolor punzante", "dull": "un dolor sordo",
    "burning": "ardor", "throbbing": "un dolor que late", "diffuse": "una molestia general",
}
ONSET_ES = {"sudden": "de repente", "gradual": "poco a poco"}
RADIATION_ES = {
    "left_arm": "el brazo izquierdo", "jaw": "la mandíbula", "neck": "el cuello", "back": "la espalda",
    "abdomen": "el abdomen", "chest": "el pecho",
}
RED_FLAG_ES = {
    "chest_pain": "dolor de pecho", "dyspnea": "falta de aire", "syncope": "desmayo o casi desmayo",
    "uncontrolled_bleeding": "sangrado", "stroke_signs": "debilidad en la cara o en un brazo",
    "diaphoresis": "sudor frío",
}


def _join_es(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def _to(phrase: str) -> str:
    """'el brazo' -> 'al brazo', 'la mandíbula' -> 'a la mandíbula' (Spanish contraction)."""
    return "al " + phrase[3:] if phrase.startswith("el ") else "a " + phrase


def _duration_es(hours: float | None) -> str | None:
    if hours is None:
        return None
    if hours < 1:
        return "hace menos de una hora"
    if hours < 36:
        h = round(hours)
        return "hace un día" if h == 24 else ("hace una hora" if h == 1 else f"hace unas {h} horas")
    days = round(hours / 24)
    return f"hace unos {days} días"


def readback_es(chart: ExtractionResult) -> list[str]:
    """Short Spanish sentences, in read-back order, ending with the confirmation question."""
    lines: list[str] = []
    loc = LOCATION_ES.get(chart.location)
    qual = QUALITY_ES.get(chart.quality)
    if qual and loc:
        lines.append(f"Usted siente {qual} en {loc}.")
    elif loc:
        lines.append(f"Usted tiene una molestia en {loc}.")
    elif qual:
        lines.append(f"Usted siente {qual}.")

    onset, dur = ONSET_ES.get(chart.onset), _duration_es(chart.timing_duration_hours)
    if onset and dur:
        lines.append(f"Empezó {onset}, {dur}.")
    elif onset or dur:
        lines.append(f"Empezó {onset or dur}.")

    rad = [RADIATION_ES[r] for r in chart.radiation if r in RADIATION_ES]
    if rad:
        lines.append(f"Se le corre {_join_es([_to(r) for r in rad])}.")
    elif chart.radiation == ["none"] and chart.source_phrases.radiation:
        lines.append("No se le corre a otra parte.")

    if chart.severity_1_to_10 is not None:
        lines.append(f"Del 1 al 10, es un {chart.severity_1_to_10}.")

    if chart.source_phrases.provocation:
        lines.append(f"Usted dijo: «{chart.source_phrases.provocation.strip()}».")

    flags = [RED_FLAG_ES[f] for f in chart.red_flag_symptoms if f in RED_FLAG_ES and f != "chest_pain"]
    if flags:
        lines.append(f"También tiene {_join_es(flags)}.")

    lines.append("¿Es correcto?")
    return lines
