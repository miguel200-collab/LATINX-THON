"""Streamlit demo: ambient ER intake -> nurse confirmation sheet.

    uv run streamlit run app.py

Administrative intake aid. Not a diagnosis. The RN assigns ESI. All demo data is synthetic.
Anything that is not live model output is labeled in the banner, on the sheet, and in the JSON.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from triage import asr, fixtures
from triage.charts import loss_chart, probability_chart, queue_chart
from triage.config import OUTPUT_DIR, get_settings
from triage.erlang import max_stable_intake_minutes, spec_scenarios
from triage.pdf_sheet import render_preview
from triage.pipeline import PipelineError, run_pipeline

st.set_page_config(page_title="Ambient ER intake", page_icon=None, layout="wide")

SOURCE_OPTIONS = {
    "auto": "Auto: live where keys exist, stored fixtures otherwise (always labeled)",
    "offline": "Offline: never call an API (stored fixtures only)",
    "outage": "Simulate an API outage: conservative ESI 2 safety hold",
}


@st.cache_resource(show_spinner="Loading the speech model (about 10 s the first time)...")
def warm_speech_model(size: str) -> str:
    """Load Whisper once at startup so the first click is not slow."""
    if asr.is_model_cached(size):
        asr._load(size)
        return "ready"
    return "not downloaded"


def _save_upload(file, folder_name: str = "uploads") -> str:
    folder = OUTPUT_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", getattr(file, "name", "recording.wav") or "recording.wav")
    path = folder / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe}"
    path.write_bytes(file.getvalue())
    return str(path)


def _fmt_wait(metrics) -> str:
    if not metrics.stable:
        return "never clears"
    return f"{metrics.wait_minutes:.1f} min" if metrics.wait_minutes >= 1 else f"{metrics.wait_seconds:.0f} s"


settings = get_settings()
st.title("Ambient ER intake: nurse confirmation sheet")
st.caption("Administrative intake aid. Not a diagnosis. The RN assigns ESI. All demo data is synthetic.")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Run mode")
    mode = st.radio("How should it run?", list(SOURCE_OPTIONS), format_func=SOURCE_OPTIONS.get, label_visibility="collapsed")
    st.divider()
    st.subheader("Status")
    st.write(f"Gemini key: **{'set' if settings.google_api_key else 'not set'}**")
    st.write(f"Jev key: **{'set' if settings.typesafe_api_key else 'not set'}**")
    model_ready = asr.is_model_cached(settings.whisper_model)
    st.write(f"Speech model ({settings.whisper_model}): **{'downloaded' if model_ready else 'not downloaded'}**")
    if not settings.google_api_key or not settings.typesafe_api_key:
        st.info("Missing keys are fine: those steps use stored fixtures and say so. Add keys to `.env` to go live.")
    st.caption(f"gemini `{settings.gemini_model}` | jev `{settings.jev_model}`")
    if not os.getenv("TRIAGE_SKIP_WARMUP") and model_ready:
        warm_speech_model(settings.whisper_model)

tab_intake, tab_queue = st.tabs(["Intake demo", "Queue math"])

# ---------------------------------------------------------------- intake tab
with tab_intake:
    options = [*fixtures.FIXTURE_IDS, "custom", "upload", "mic"]
    labels = {
        **{fid: fixtures.title(fid) for fid in fixtures.FIXTURE_IDS},
        "custom": "Type or paste a Spanish transcript",
        "upload": "Upload an audio file",
        "mic": "Record with the microphone",
    }
    choice = st.selectbox("Case", options, format_func=labels.get)

    run_args: dict = {}
    ready = True
    if choice in fixtures.FIXTURE_IDS:
        clip = fixtures.audio_path(choice)
        use_audio = False
        if clip is not None:
            use_audio = st.toggle(
                "Run speech-to-text on the audio clip",
                value=model_ready,
                disabled=not model_ready,
                help="Uses local Whisper. Off: use the stored transcript.",
            )
            st.audio(str(clip))
            if not model_ready:
                st.caption("Speech model not downloaded: `uv run python -m triage.cli prefetch`")
        with st.expander("Stored transcript"):
            st.write(fixtures.load_transcript(choice))
        run_args = {"fixture_id": choice, "audio_path": str(clip) if (clip and use_audio) else None}
    elif choice == "custom":
        text = st.text_area("Spanish transcript", height=140, placeholder="Doctora, me duele el pecho desde hace una hora...")
        ready = bool(text.strip())
        run_args = {"transcript": text}
    elif choice == "upload":
        up = st.file_uploader("Audio file", type=["wav", "mp3", "m4a", "ogg", "flac", "webm", "aac"])
        ready = up is not None
        if up is not None:
            st.audio(up)
            run_args = {"audio_path": _save_upload(up)}
    else:  # mic
        rec = st.audio_input("Record the patient") if hasattr(st, "audio_input") else None
        ready = rec is not None
        if rec is None and not hasattr(st, "audio_input"):
            st.warning("This Streamlit version has no microphone widget. Use an upload.")
        if rec is not None:
            run_args = {"audio_path": _save_upload(rec)}

    if st.button("Run intake", type="primary", disabled=not ready):
        try:
            with st.spinner("Running intake..."):
                st.session_state["result"] = run_pipeline(mode=mode, **run_args)
            st.session_state.pop("error", None)
        except PipelineError as exc:
            st.session_state.pop("result", None)
            st.session_state["error"] = str(exc)

    if st.session_state.get("error"):
        st.error(f"Could not run the intake: {st.session_state['error']}")

    r = st.session_state.get("result")
    if r is not None:
        flag, chart = r.flag, r.extraction.chart
        banner = st.success if r.label_kind == "live" else (st.warning if r.label_kind == "fixture" else st.error)
        banner("**" + r.headline_label + "**\n\n" + "\n".join(f"- {line}" for line in r.step_lines))

        m1, m2 = st.columns(2)
        m1.metric("Model's most likely tier", "not available" if flag.raw_argmax_tier is None else f"ESI {flag.raw_argmax_tier}")
        m2.metric("SUGGESTED REVIEW TIER", f"ESI {flag.suggested_review_tier}")
        m3, m4 = st.columns(2)
        m3.metric("Jev confidence", "n/a" if flag.jev_confidence is None else f"{flag.jev_confidence:.2f}")
        m4.metric("Time, button to sheet", f"{r.latency_ms.get('total', 0) / 1000:.1f} s")
        if flag.probabilities is None:
            st.caption("No probabilities for this case: conservative safety hold. The nurse takes the history directly.")
        elif flag.override_triggered:
            st.caption(f"The safety rule raised the tier from ESI {flag.raw_argmax_tier} to ESI {flag.suggested_review_tier} "
                       "(under-triage costs 10x over-triage). It is a flag; the nurse assigns the ESI.")
        else:
            st.caption("The safety rule agrees with the most likely tier. The nurse assigns the ESI.")

        left, right = st.columns([1, 1])
        with left:
            st.subheader("Nurse sheet")
            if r.pdf_path and r.pdf_path.exists():
                st.image(render_preview(r.pdf_path, scale=1.4), width="stretch")
                d1, d2 = st.columns(2)
                d1.download_button("PDF", r.pdf_path.read_bytes(), file_name=r.pdf_path.name, mime="application/pdf",
                                   help="Download the nurse sheet")
                d2.download_button("JSON", r.json_path.read_bytes(), file_name=r.json_path.name, mime="application/json",
                                   help="Download the structured result")
        with right:
            if flag.probabilities is not None:
                st.caption("Loss rule: under-triage costs 10x, over-triage 1x. The tier with the lowest expected loss is "
                           "the suggested review tier (red).")
                st.plotly_chart(probability_chart(flag.probabilities, flag.suggested_review_tier, flag.raw_argmax_tier), width="stretch")
                st.plotly_chart(loss_chart(flag.expected_losses, flag.suggested_review_tier), width="stretch")

            st.subheader("Read-back table")
            sp = chart.source_phrases
            rows = [
                ("Location", chart.location, sp.location, "location"),
                ("Onset", chart.onset, sp.onset, "onset"),
                ("Provocation", chart.provocation, sp.provocation, "provocation"),
                ("Quality", chart.quality, sp.quality, "quality"),
                ("Radiation", ", ".join(chart.radiation), sp.radiation, "radiation"),
                ("Severity", "not stated" if chart.severity_1_to_10 is None else f"{chart.severity_1_to_10}/10", sp.severity_1_to_10, "severity_1_to_10"),
                ("Duration", "not stated" if chart.timing_duration_hours is None else f"{chart.timing_duration_hours:g} hours", sp.timing_duration_hours, "timing_duration_hours"),
                ("Red flags", ", ".join(chart.red_flag_symptoms) or "none", sp.red_flag_symptoms, "red_flag_symptoms"),
            ]
            st.dataframe(
                pd.DataFrame({
                    "Field": [x[0] for x in rows],
                    "Extracted": [x[1].replace("_", " ") for x in rows],
                    "Patient's own words": [x[2] or "-" for x in rows],
                    "Check": ["NOT FOUND in transcript" if x[3] in r.extraction.unverified_quotes else "ok" for x in rows],
                }),
                hide_index=True, width="stretch",
            )
            st.caption(chart.raw_summary_en)

        st.subheader("Latency")
        st.dataframe(
            pd.DataFrame({"Step": list(r.latency_ms), "Milliseconds": [round(v, 1) for v in r.latency_ms.values()]}),
            hide_index=True,
        )
        if r.latency_ms.get("asr_model_load"):
            st.caption("The speech model was loaded during this run; later runs skip that time.")
        with st.expander("Transcript"):
            st.write(f"Source: {r.transcript_source}")
            st.write(r.transcript)
        if r.notes:
            with st.expander("Notes"):
                for n in r.notes:
                    st.write("- " + n)
        with st.expander("Saved JSON"):
            st.json(r.to_dict())

# ---------------------------------------------------------------- queue tab
with tab_queue:
    st.subheader("Waiting-room queue (Erlang-C, M/M/c)")
    c1, c2, c3, c4 = st.columns(4)
    arrivals = c1.slider("Patients arriving per hour", 1, 60, 28)
    nurses = c2.slider("Triage nurses", 1, 10, 4)
    manual = c3.slider("Manual intake (min/patient)", 2.0, 15.0, 8.0, 0.1)
    auto = c4.slider("Automated intake (min/patient)", 1.0, 10.0, 3.5, 0.1)
    sc = spec_scenarios(arrivals, nurses, manual, auto)
    a, b, c = st.columns(3)
    a.metric("Manual: average wait", _fmt_wait(sc["manual"]), f"utilization {sc['manual'].utilization * 100:.0f}%", delta_color="off")
    b.metric("Automated: average wait", _fmt_wait(sc["automated"]), f"utilization {sc['automated'].utilization * 100:.0f}%", delta_color="off")
    c.metric("Wait reduction", "n/a" if sc["wait_reduction"] is None else f"{sc['wait_reduction'] * 100:.1f}%")
    st.plotly_chart(queue_chart(arrivals, nurses, manual, auto), width="stretch")
    st.caption(
        f"Slowest intake that keeps the queue stable: {max_stable_intake_minutes(arrivals, nurses):.2f} min/patient. "
        "These inputs are modeling assumptions from the spec, not measurements. "
        "The spec printed a 34.8 minute wait for the default manual case; the formula gives 25.7."
    )
