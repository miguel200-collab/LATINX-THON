"""Data contracts (HACKATHON_TEST_DRIVE.md section 3).

Contract 1: ExtractionResult (what Gemini returns, validated here).
Contract 3: TriageFlag (what Python decides after Jev and the loss rule).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Location = Literal[
    "chest", "upper_abdomen", "lower_abdomen", "head", "neck", "back",
    "shoulder_arm", "hand", "hip_leg", "knee", "ankle_foot", "other", "unknown",
]
Onset = Literal["sudden", "gradual", "unknown"]
Quality = Literal[
    "crushing_pressure", "sharp", "dull", "burning", "throbbing", "diffuse", "unknown",
]
Radiation = Literal["left_arm", "jaw", "neck", "back", "abdomen", "chest", "none"]
RedFlag = Literal[
    "chest_pain", "dyspnea", "syncope", "uncontrolled_bleeding", "stroke_signs", "diaphoresis",
]

LOCATION_VALUES = list(Location.__args__)
ONSET_VALUES = list(Onset.__args__)
QUALITY_VALUES = list(Quality.__args__)
RADIATION_VALUES = list(Radiation.__args__)
RED_FLAG_VALUES = list(RedFlag.__args__)

# Fields that carry a verbatim Spanish quote (same names as the chart fields).
QUOTE_FIELDS = [
    "location", "onset", "provocation", "quality", "radiation",
    "severity_1_to_10", "timing_duration_hours", "red_flag_symptoms",
]


class SourcePhrases(BaseModel):
    """Verbatim Spanish words the patient used, one per field. None when not quotable."""

    location: Optional[str] = None
    onset: Optional[str] = None
    provocation: Optional[str] = None
    quality: Optional[str] = None
    radiation: Optional[str] = None
    severity_1_to_10: Optional[str] = None
    timing_duration_hours: Optional[str] = None
    red_flag_symptoms: Optional[str] = None


class ExtractionResult(BaseModel):
    location: Location = "unknown"
    onset: Onset = "unknown"
    provocation: str = "none stated"
    quality: Quality = "unknown"
    radiation: list[Radiation] = Field(default_factory=lambda: ["none"])
    severity_1_to_10: Optional[int] = Field(default=None, ge=1, le=10)
    timing_duration_hours: Optional[float] = Field(default=None, ge=0)
    red_flag_symptoms: list[RedFlag] = Field(default_factory=list)
    source_phrases: SourcePhrases = Field(default_factory=SourcePhrases)
    raw_summary_en: str = ""

    @field_validator("provocation", mode="before")
    @classmethod
    def _provocation_text(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return "none stated"
        return value

    @field_validator("radiation", mode="before")
    @classmethod
    def _radiation_list(cls, value):
        if value is None:
            return ["none"]
        if isinstance(value, str):
            return [value]
        return value

    @model_validator(mode="after")
    def _normalize(self):
        # "none" excludes everything else; an empty list means none.
        rad = list(dict.fromkeys(self.radiation))
        if not rad:
            rad = ["none"]
        if "none" in rad and len(rad) > 1:
            rad = [r for r in rad if r != "none"]
        self.radiation = rad
        self.red_flag_symptoms = list(dict.fromkeys(self.red_flag_symptoms))
        return self

    def jev_state(self) -> dict:
        """The structured fields Jev is allowed to see (Contract 2).

        Excludes raw_summary_en and source_phrases: generated text could carry an
        invented inference, and unrelated state lowers Jev's accuracy.
        """
        return {
            "symptoms": {
                "location": self.location,
                "onset": self.onset,
                "provocation": self.provocation,
                "quality": self.quality,
                "radiation": list(self.radiation),
                "severity_1_to_10": self.severity_1_to_10,
                "timing_duration_hours": self.timing_duration_hours,
                "red_flag_symptoms": list(self.red_flag_symptoms),
            }
        }


class TriageFlag(BaseModel):
    """Python's decision output (Contract 3). The nurse assigns the official ESI."""

    probabilities: Optional[list[float]] = None
    raw_argmax_tier: Optional[int] = None
    suggested_review_tier: int
    expected_losses: Optional[list[float]] = None
    override_triggered: bool = False
    jev_confidence: Optional[float] = None
    source: Literal["jev", "fixture", "regex_hold", "gemini_acuity"]
    latency_ms: dict[str, float] = Field(default_factory=dict)
