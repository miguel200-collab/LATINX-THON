# LATINX-THON: Ambient ER Triage (Sala de Emergencias)

Spanish-speaking patients answer six short clinical intake questions on their phone (WhatsApp-style voice notes or typing). A Python backend converts their responses into a clinical chart, scores it via TypeSafe Jev, applies an asymmetric loss model (punishing undertriage 10×), and provides an ER nurse workstation with an intake summary sheet to confirm and sign.

## Architecture & Visual Identities

1. **Patient Interface (Base44 `patient`):** WhatsApp-style mobile chat (`#008069`, beige dots background `#efeae2`, hold/lock/cancel voice notes). Zero AI replies or triage levels shown to patients.
2. **Nurse Station (Base44 `nurse`):** Windows 7/10 clinical workstation EHR aesthetic (`#1a3a6b` Aero header, beveled buttons, Segoe UI). Suggested review tier, 5 ESI probabilities with loss bars, Spanish read-back script, official ESI buttons (1–5), and printable confirmation PDF.
3. **Engine (Python / FastAPI):**
   - **ASR:** Local `faster-whisper` (`small` model, CPU int8, Spanish).
   - **Extraction:** Gemini 3.8 Flash dialect-to-JSON OPQRST extraction with regex safety hold.
   - **Acuity Scoring:** TypeSafe Jev Choice evaluating structured clinical symptoms.
   - **Safety Math:** Asymmetric expected loss gate (`C_UNDER=10`, `C_OVER=1`) to prevent undertriage.
   - **Operations:** Erlang-C queue model for ED waiting room time reduction.
   - **PDF:** ReportLab one-page clinical intake and signed review sheets.

## Verification & Quickstart

```bash
uv sync
uv run python -c "import fastapi, faster_whisper, reportlab, google.genai, typesafe_sdk"
uv run pytest -q
```
