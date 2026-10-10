"""The patient's questions: six short Spanish questions, asked the way a triage nurse would.

Each question covers one or two parts of the chart, so six questions fill all eight OPQRST fields.
Questions can turn green without being asked directly when an earlier answer already covered all
of their parts ("auto_cover"). The opening question and the red-flag question are always asked
directly: the red-flag question must never be skipped on a guess.
"""

from __future__ import annotations

QUESTIONS: list[dict] = [
    {
        "id": "q1",
        "es": "Cuéntenos qué le pasa hoy.",
        "en": "What brings you in today?",
        "icon": "chat",
        "parts": ["complaint"],
        "auto_cover": False,
    },
    {
        "id": "q2",
        "es": "¿Dónde le duele o le molesta? ¿Se le corre a otra parte?",
        "en": "Where does it hurt, and does it spread anywhere?",
        "icon": "body",
        "parts": ["location", "radiation"],
        "auto_cover": True,
    },
    {
        "id": "q3",
        "es": "¿Cuándo empezó? ¿Fue de repente o poco a poco?",
        "en": "When did it start? Suddenly or gradually?",
        "icon": "clock",
        "parts": ["onset", "duration"],
        "auto_cover": True,
    },
    {
        "id": "q4",
        "es": "¿Cómo es la molestia y qué tan fuerte es, del 1 al 10?",
        "en": "What does it feel like, and how strong is it from 1 to 10?",
        "icon": "scale",
        "parts": ["quality", "severity"],
        "auto_cover": True,
    },
    {
        "id": "q5",
        "es": "¿Algo lo empeora o lo mejora?",
        "en": "Does anything make it worse or better?",
        "icon": "arrows",
        "parts": ["provocation"],
        "auto_cover": True,
    },
    {
        "id": "q6",
        "es": "¿Tiene falta de aire, mareo o desmayo, sudor frío, sangrado, o debilidad en la cara o en un brazo?",
        "en": "Any shortness of breath, dizziness or fainting, cold sweat, bleeding, or weakness in the face or an arm?",
        "icon": "alert",
        "parts": ["red_flags"],
        "auto_cover": False,
    },
]

QUESTION_IDS = [q["id"] for q in QUESTIONS]
BY_ID = {q["id"]: q for q in QUESTIONS}

PART_LABELS = {
    "complaint": ("lo que le pasa", "complaint"),
    "location": ("dónde", "location"),
    "radiation": ("se corre", "radiation"),
    "onset": ("cómo empezó", "onset"),
    "duration": ("cuándo", "duration"),
    "quality": ("cómo es", "quality"),
    "severity": ("1 al 10", "severity"),
    "provocation": ("qué lo cambia", "provocation"),
    "red_flags": ("señales de alarma", "red flags"),
}


def public_questions() -> list[dict]:
    """The list the screens show (Spanish text, English gloss for the nurse and judges)."""
    return [
        {
            "id": q["id"], "es": q["es"], "en": q["en"], "icon": q["icon"], "auto_cover": q["auto_cover"],
            "parts": [{"id": p, "es": PART_LABELS[p][0], "en": PART_LABELS[p][1]} for p in q["parts"]],
        }
        for q in QUESTIONS
    ]
