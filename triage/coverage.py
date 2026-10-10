"""Which questions are answered? A deterministic keyword check over the patient's own words.

No AI is involved and nothing is said back to the patient: this only decides which question bubbles
turn green. A question is green when the patient answered it directly, or (for auto_cover questions)
when every one of its parts was already mentioned in earlier answers. Partly covered questions stay
gray and show which parts are done. The chart itself is still built by Gemini at the end.
"""

from __future__ import annotations

import re

from .fixtures import normalize_text
from .questions import QUESTIONS

NUM = r"(?:\d{1,2}|uno|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"

PART_PATTERNS: dict[str, list[str]] = {
    "location": [
        r"\b(pecho|estomago|barriga|panza|abdomen|vientre|cabeza|espalda|cuello|garganta|brazo|brazos|pierna|piernas|"
        r"rodilla|tobillo|pie|pies|mano|manos|hombro|cadera|costado|oido|oidos|ojo|ojos|muela|diente|cintura|nuca|"
        r"frente|torax|ingle|codo|muneca|dedo|dedos|corazon|rinon|rinones|vejiga)\b",
    ],
    "radiation": [
        r"se me (corre|va|pasa|sube|baja|extiende)", r"\bse (corre|va|pasa|sube|baja|extiende)\b",
        r"\b(corre|sube|baja) (pal|para el|para la|hacia|al|a la)\b", r"\bhasta (el|la|los|las)\b",
        r"\bhacia (el|la|los|las)\b", r"no se (me )?(corre|va|pasa|mueve)", r"\bno me duele nada mas\b",
        r"\bsolo (ahi|aqui|en)\b", r"\bnada mas (ahi|aqui|en)\b", r"\bno se mueve\b",
    ],
    "onset": [
        r"\bde (repente|golpe|pronto|un momento a otro)\b", r"\bpoco a poco\b", r"\bme (dio|empezo|comenzo|agarro)\b",
        r"\b(empezo|comenzo|inicio)\b", r"\bme (torci|cai|pegue|golpee|corte|queme)\b", r"\bdesde que\b",
        r"\bde la nada\b", r"\bfue (rapido|lento|subito)\b",
    ],
    "duration": [
        rf"\bhace {NUM}( o {NUM})? (minuto|minutos|hora|horas|dia|dias|semana|semanas|mes|meses)\b",
        rf"\bhace (como|unos|unas|mas de|menos de|casi) ({NUM} )?(minuto|minutos|hora|horas|dia|dias|semana|semanas|mes|meses|rato|ratito)\b",
        r"\bhace (un rato|rato|poco|ratito|mucho)\b",
        rf"\b{NUM} (minuto|minutos|hora|horas|dia|dias|semana|semanas)\b",
        r"\bdesde (ayer|anoche|hoy|esta manana|esta tarde|la manana|la noche|el (lunes|martes|miercoles|jueves|viernes|sabado|domingo))\b",
        r"\b(ayer|anoche|anteayer|antier|esta manana|esta tarde|esta noche)\b", r"\ba las {NUM}\b".replace("{NUM}", NUM),
    ],
    "quality": [
        r"\b(aprieta|apreton|apretado|presion|opresion|piedra|peso|pesadez|aplasta)\b",
        r"\b(punzante|pinchazo|pinchazos|punzada|punzadas|clavo|cuchillo|navaja|filoso|agudo)\b",
        r"\b(arde|ardor|quema|quemazon|acidez|agruras)\b", r"\b(late|palpita|pulsa|punza|martillo)\b",
        # Not "molestia", "se me hinchó" or "como un ...": too generic, and "como un cinco de diez" is a severity.
        r"\b(sordo|colico|calambre|hormigueo|adormecido|entumido)\b",
        r"\bcomo si\b",
    ],
    "severity": [
        # Never a bare "diez": "a las diez de la mañana" is a time, not a score.
        rf"\b{NUM} de (10|diez)\b", rf"\b{NUM} (sobre|/) ?(10|diez)\b", rf"\bun {NUM}\b",
        r"\b(insoportable|muy fuerte|fuertisimo|leve|poquito|aguantable|horrible|terrible|el peor)\b",
    ],
    "provocation": [
        # Not a bare "quita": "una acidez que no se quita" means it persists, not what changes it.
        r"\b(empeora|empeoro|peor|mejora|mejoro|alivia|calma|aumenta|disminuye)\b",
        r"\bse (me |le )?quita (cuando|con|si|al)\b",
        r"\bcuando (lo |la |le |me )?(camino|respiro|como|apoyo|muevo|acuesto|levanto|toso|hago|subo|trabajo|piso|agacho|toco)\b",
        r"\b(en reposo|sentad[oa]|acostad[oa]|parad[oa]|no hice esfuerzo|haciendo esfuerzo|al caminar|al respirar|al comer|al apoyar)\b",
        r"\bnada lo (mejora|empeora|cambia|quita)\b", r"\bno se (que|si) lo (empeora|mejora)\b",
    ],
}


def _hits(text: str, part: str) -> bool:
    norm = normalize_text(text)
    return any(re.search(p, norm) for p in PART_PATTERNS.get(part, []))


def compute_state(answers: list[dict]) -> dict:
    """answers: [{"question_id": "q1", "text": "..."}, ...] -> per-question status, next question, done.

    status: "answered" (asked and answered), "covered" (every part already mentioned elsewhere),
    "partial" (some parts mentioned), "pending". Green = answered or covered.
    """
    texts = [a.get("text", "") for a in answers if a.get("text", "").strip()]
    answered = {a["question_id"] for a in answers if a.get("text", "").strip()}
    state: dict[str, dict] = {}
    for q in QUESTIONS:
        if q["id"] in answered:
            parts = {p: True for p in q["parts"]}
            status = "answered"
        else:
            parts = {p: any(_hits(t, p) for t in texts) if p in PART_PATTERNS else False for p in q["parts"]}
            if q["auto_cover"] and all(parts.values()):
                status = "covered"
            elif any(parts.values()):
                status = "partial"
            else:
                status = "pending"
        state[q["id"]] = {"status": status, "parts": parts, "green": status in ("answered", "covered")}
    pending = [q["id"] for q in QUESTIONS if not state[q["id"]]["green"]]
    return {"questions": state, "next": pending[0] if pending else None, "done": not pending}
