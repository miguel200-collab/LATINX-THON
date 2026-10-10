"""Command line for the intake pipeline.

    uv run python -m triage.cli doctor [--live]           check the environment (and, with --live, the two APIs)
    uv run python -m triage.cli demo                      the two-case demo: chest pressure, then ankle sprain
    uv run python -m triage.cli run --fixture A           one intake from a stored case
    uv run python -m triage.cli run --text "..."          one intake from typed Spanish
    uv run python -m triage.cli run --audio clip.wav      one intake from an audio file
    uv run python -m triage.cli check-extraction          live Gemini vs the gold values (needs GOOGLE_API_KEY)
    uv run python -m triage.cli jev-sanity                live Jev sanity checks (needs TYPESAFE_API_KEY)
    uv run python -m triage.cli erlang                    the queue numbers
    uv run python -m triage.cli transcribe clip.wav       speech-to-text only
    uv run python -m triage.cli prefetch                  download the Whisper model once

Administrative intake aid. Not a diagnosis. The RN assigns ESI.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import sys
from pathlib import Path

from . import asr, fixtures
from .checks import check_gold, fields_without_quote, verify_quotes
from .config import FIXTURES_DIR, OUTPUT_DIR, ROOT, get_settings
from .erlang import max_stable_intake_minutes, spec_scenarios
from .extraction import MODES, ExtractionError, extract_live
from .jev import run_sanity, score_live
from .pipeline import PipelineError, PipelineResult, run_pipeline
from .util import ApiTimeout, elapsed_ms, mask_secrets, now

PACKAGES = [
    "numpy", "pydantic", "reportlab", "plotly", "streamlit", "google-genai",
    "typesafe-sdk", "faster-whisper", "av", "pypdfium2", "python-dotenv",
]


def _pretty(value: str) -> str:
    return value.replace("_", " ")


def print_result(r: PipelineResult) -> None:
    chart, flag = r.extraction.chart, r.flag
    print(f"\n=== {r.case_label} ===")
    print(f"  LABEL: {r.headline_label}")
    for line in r.step_lines:
        print(f"    {line}")
    snippet = r.transcript if len(r.transcript) < 220 else r.transcript[:217] + "..."
    print(f"  Transcript ({r.transcript_source}): {snippet}")
    sev = "not stated" if chart.severity_1_to_10 is None else f"{chart.severity_1_to_10}/10"
    dur = "not stated" if chart.timing_duration_hours is None else f"{chart.timing_duration_hours:g} hours"
    print(
        f"  Chart: {_pretty(chart.location)} | {chart.onset} | {_pretty(chart.quality)} | "
        f"radiation {', '.join(_pretty(x) for x in chart.radiation)} | severity {sev} | {dur}"
    )
    print(f"         red flags: {', '.join(_pretty(x) for x in chart.red_flag_symptoms) or 'none'}")
    if r.extraction.unverified_quotes:
        print(f"         quotes NOT found in the transcript: {', '.join(r.extraction.unverified_quotes)}")
    if flag.probabilities is not None:
        print("  Probabilities:  " + " | ".join(f"ESI {i + 1} {p * 100:.0f}%" for i, p in enumerate(flag.probabilities)))
        print("  Expected loss:  " + " | ".join(f"{x:.2f}" for x in flag.expected_losses))
        verdict = "safety rule raised the tier" if flag.override_triggered else "safety rule agrees"
        conf = f"  Jev confidence {flag.jev_confidence:.2f}" if flag.jev_confidence is not None else ""
        print(f"  Most likely tier: ESI {flag.raw_argmax_tier}   SUGGESTED REVIEW TIER: ESI {flag.suggested_review_tier}   ({verdict}){conf}")
    else:
        print(f"  No probabilities.   SUGGESTED REVIEW TIER: ESI {flag.suggested_review_tier}   (conservative safety hold)")
    print("  Official ESI: left blank for the RN to assign.")
    print("  Latency ms: " + " | ".join(f"{k} {v:g}" for k, v in r.latency_ms.items()))
    for note in r.notes:
        print(f"  Note: {note}")
    if r.pdf_path:
        print(f"  Files: {r.pdf_path}\n         {r.json_path}")


def _warm_whisper_if_cached() -> bool:
    if asr.is_model_cached():
        asr._load(get_settings().whisper_model)
        return True
    return False


def cmd_doctor(args) -> int:
    s = get_settings()
    problems = 0
    print("Ambient ER triage - environment check\n")
    print(f"  Python            {sys.version.split()[0]}")
    missing = []
    versions = []
    for pkg in PACKAGES:
        try:
            versions.append(f"{pkg} {metadata.version(pkg)}")
        except metadata.PackageNotFoundError:
            missing.append(pkg)
    print(f"  Packages          {'ALL INSTALLED' if not missing else 'MISSING: ' + ', '.join(missing) + '  (run: uv sync)'}")
    problems += bool(missing)

    ids_ok = all(
        (FIXTURES_DIR / "transcripts" / f"{i}.txt").exists() and (FIXTURES_DIR / "charts" / f"{i}.json").exists()
        for i in fixtures.FIXTURE_IDS
    )
    audio_n = sum(1 for i in fixtures.FIXTURE_IDS if fixtures.audio_path(i))
    print(f"  Fixtures          {'ok' if ids_ok else 'INCOMPLETE'}; audio clips: {audio_n}/{len(fixtures.FIXTURE_IDS)}"
          + ("" if audio_n == len(fixtures.FIXTURE_IDS) else "  (run: ./scripts/make_synthetic_audio.sh)"))
    problems += not ids_ok

    cached = asr.is_model_cached()
    print(f"  Whisper model     {s.whisper_model}: " + ("downloaded (works offline)" if cached else
          "NOT downloaded  (run: uv run python -m triage.cli prefetch)"))
    problems += not cached

    print(f"  GOOGLE_API_KEY    {'set' if s.google_api_key else 'NOT SET  -> Gemini step uses stored fixture charts'}")
    print(f"  TYPESAFE_API_KEY  {'set' if s.typesafe_api_key else 'NOT SET  -> Jev step uses stored fixture probabilities'}")
    if s.force_offline:
        print("  TRIAGE_OFFLINE    1 -> no API will be called")
    live_g, live_j = s.gemini_live_ready, s.jev_live_ready
    print(f"  Run mode now      {'FULLY LIVE' if live_g and live_j else ('PARTLY LIVE' if live_g or live_j else 'OFFLINE (stored fixtures, labeled)')}")
    print(f"  Models            gemini {s.gemini_model} | jev {s.jev_model} | whisper {s.whisper_model}")
    print(f"  Timeouts          gemini {s.gemini_timeout_s:g} s | jev {s.jev_timeout_s:g} s")
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        probe = OUTPUT_DIR / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        print(f"  Output folder     {OUTPUT_DIR.relative_to(ROOT)}/ (writable)")
    except OSError as exc:
        print(f"  Output folder     NOT WRITABLE: {exc}")
        problems += 1

    if args.live:
        print("\nLive checks (these make real API calls):")
        transcript = fixtures.load_transcript("A")
        if not s.google_api_key:
            print("  Gemini: skipped (no GOOGLE_API_KEY)")
        else:
            t = now()
            try:
                chart, _ = extract_live(transcript, s)
                fails = check_gold(chart, fixtures.load_gold("A"))
                print(f"  Gemini: answered in {elapsed_ms(t):g} ms; gold check "
                      + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
                problems += bool(fails)
            except Exception as exc:
                print(f"  Gemini: FAILED ({type(exc).__name__}): {mask_secrets(str(exc), s.google_api_key)[:200]}")
                problems += 1
        if not s.typesafe_api_key:
            print("  Jev: skipped (no TYPESAFE_API_KEY)")
        else:
            try:
                o = score_live(fixtures.load_chart("A"), s)
                print(f"  Jev: answered in {o.latency_ms:g} ms ({o.model}); probabilities "
                      + ", ".join(f"{p:.2f}" for p in o.probabilities) + f"; confidence {o.confidence}")
            except Exception as exc:
                print(f"  Jev: FAILED ({type(exc).__name__}): {mask_secrets(str(exc), s.typesafe_api_key)[:200]}")
                problems += 1
    else:
        print("\n  (add --live to make one real call to each API once keys are set)")
    print("\n" + ("All good." if not problems else f"{problems} problem(s) found - see above."))
    return 1 if problems else 0


def cmd_run(args) -> int:
    transcript = args.text
    if args.text_file:
        transcript = Path(args.text_file).read_text(encoding="utf-8")
    try:
        result = run_pipeline(
            transcript=transcript, audio_path=args.audio, fixture_id=args.fixture, mode=args.mode,
            make_pdf=not args.no_pdf, out_dir=args.out,
        )
    except PipelineError as exc:
        print(f"Could not run the intake: {exc}", file=sys.stderr)
        return 2
    print_result(result)
    return 0


def cmd_demo(args) -> int:
    use_audio = not args.no_audio and asr.is_model_cached()
    if not args.no_audio and not use_audio:
        print("(Whisper model not downloaded: using stored transcripts. Run `prefetch` to enable the audio step.)")
    if use_audio:
        print("Warming the speech model (first load takes about 10 s)...")
        _warm_whisper_if_cached()
    rows = []
    for fid in args.cases:
        audio = fixtures.audio_path(fid) if use_audio else None
        result = run_pipeline(audio_path=audio, fixture_id=fid, mode=args.mode, out_dir=args.out)
        print_result(result)
        rows.append(result)
    print("\n--- Demo summary ---")
    print(f"{'Case':<48} {'Most likely':<12} {'Suggested':<10} {'Label'}")
    for r in rows:
        ml = "-" if r.flag.raw_argmax_tier is None else f"ESI {r.flag.raw_argmax_tier}"
        print(f"{r.case_label:<48} {ml:<12} ESI {r.flag.suggested_review_tier:<6} {r.headline_label}")
    return 0


def cmd_check_extraction(args) -> int:
    s = get_settings()
    if not s.google_api_key:
        print("GOOGLE_API_KEY is not set. Put it in .env (see .env.example).", file=sys.stderr)
        return 2
    failed = 0
    for fid in args.fixtures:
        transcript = fixtures.load_transcript(fid)
        t = now()
        try:
            chart, _ = extract_live(transcript, s)
        except (ApiTimeout, ExtractionError) as exc:
            print(f"[{fid}] FAILED to get a chart: {exc}")
            failed += 1
            continue
        except Exception as exc:
            print(f"[{fid}] FAILED ({type(exc).__name__}): {mask_secrets(str(exc), s.google_api_key)[:200]}")
            failed += 1
            continue
        ms = elapsed_ms(t)
        fails = check_gold(chart, fixtures.load_gold(fid))
        bad_quotes = verify_quotes(chart, transcript)
        no_quote = fields_without_quote(chart)
        problems = fails + ([f"quotes not in transcript: {bad_quotes}"] if bad_quotes else []) + (
            [f"filled without a quote: {no_quote}"] if no_quote else [])
        print(f"[{fid}] {'PASS' if not problems else 'FAIL'}  {ms:g} ms  {s.gemini_model}")
        print(f"      chart: {chart.location} | {chart.onset} | {chart.quality} | {chart.radiation} | "
              f"{chart.severity_1_to_10} | {chart.timing_duration_hours} h | {chart.red_flag_symptoms}")
        for p in problems:
            print(f"      - {p}")
        failed += bool(problems)
    print(f"\n{len(args.fixtures) - failed}/{len(args.fixtures)} fixtures matched the gold values.")
    print("Record the results in HACKATHON_TEST_DRIVE.md section 13.4. Case C is intentionally ambiguous.")
    return 1 if failed else 0


def cmd_jev_sanity(args) -> int:
    s = get_settings()
    if not s.typesafe_api_key:
        print("TYPESAFE_API_KEY is not set. Put it in .env (see .env.example).", file=sys.stderr)
        return 2
    result = run_sanity(tuple(args.fixtures), repeats=args.repeats)
    print(f"Jev model(s): {', '.join(result['models'])}   ({args.repeats} runs per option order)\n")
    print(f"{'Case':<8} {'Order':<9} " + " ".join(f"{'ESI ' + str(i):>7}" for i in range(1, 6)))
    for fid in args.fixtures:
        for order, key in (("forward", "mean_forward"), ("reversed", "mean_reversed")):
            print(f"{fid:<8} {order:<9} " + " ".join(f"{p * 100:>6.1f}%" for p in result[key][fid]))
    print()
    failed = 0
    for check in result["checks"]:
        print(f"[{'PASS' if check['passed'] else 'FAIL'}] {check['name']}\n        {check['detail']}")
        failed += not check["passed"]
    print("\nRecord these vectors in HACKATHON_TEST_DRIVE.md section 13.4.")
    return 1 if failed else 0


def cmd_erlang(args) -> int:
    sc = spec_scenarios(args.arrivals, args.nurses, args.manual, args.automated)
    print(f"Arrivals {args.arrivals:g}/hour, {args.nurses} nurses (spec assumptions, not measurements)\n")
    for name, m in (("Manual intake", sc["manual"]), ("Automated intake", sc["automated"])):
        wait = "never clears (unstable)" if not m.stable else (
            f"{m.wait_minutes:.1f} min" if m.wait_minutes >= 1 else f"{m.wait_seconds:.0f} s")
        print(f"  {name:<17} {m.intake_minutes:g} min/patient | utilization {m.utilization * 100:.1f}% | "
              f"P(wait) {m.prob_wait * 100:.0f}% | average wait {wait}")
    if sc["wait_reduction"] is not None:
        print(f"\n  Wait reduction: {sc['wait_reduction'] * 100:.1f}%")
    print(f"  Slowest stable intake: {max_stable_intake_minutes(args.arrivals, args.nurses):.2f} min/patient")
    return 0


def cmd_transcribe(args) -> int:
    out = asr.transcribe(args.audio)
    print(out.text)
    print(f"\n[{out.model}] {out.audio_seconds} s of audio | transcribed in {out.latency_ms:g} ms"
          + (f" (+ {out.load_ms:g} ms model load)" if out.load_ms else ""))
    if args.fixture:
        wer = asr.word_error_rate(fixtures.load_transcript(args.fixture), out.text)
        print(f"Word error rate vs fixture {args.fixture}: {wer * 100:.1f}%")
    return 0


def cmd_prefetch(args) -> int:
    path = asr.prefetch_model(args.model)
    print(f"Whisper model ready: {path}")
    return 0


def cmd_bench(args) -> int:
    """Measure what the judge page shows and save it to benchmarks/latest.json (commit that file)."""
    import datetime
    import json
    import platform
    import re
    import statistics
    import subprocess
    import tempfile

    s = get_settings()
    print("Running the test suite...")
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                          capture_output=True, text=True)
    tail = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", tail)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", tail)) else 0
    print(f"  {tail}")

    rows = []
    if asr.is_model_cached():
        _warm_whisper_if_cached()
        for fid in fixtures.FIXTURE_IDS:
            clip = fixtures.audio_path(fid)
            if clip is None:
                continue
            out = asr.transcribe(clip)
            rows.append({"case": fid, "audio_seconds": out.audio_seconds, "ms": round(out.latency_ms),
                         "wer_pct": round(asr.word_error_rate(fixtures.load_transcript(fid), out.text) * 100, 1)})
            print(f"  speech-to-text {fid}: {out.latency_ms:.0f} ms, word error {rows[-1]['wer_pct']}%")
    pipeline_ms, mode_label = None, None
    with tempfile.TemporaryDirectory() as tmp:
        clip = fixtures.audio_path("A")
        r = run_pipeline(audio_path=clip if (clip and asr.is_model_cached()) else None, fixture_id="A", out_dir=tmp)
        pipeline_ms, mode_label = r.latency_ms["total"], r.headline_label
    data = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
        "whisper_model": s.whisper_model,
        "tests": {"passed": passed, "failed": failed},
        "asr": rows,
        "asr_median_ms": round(statistics.median([x["ms"] for x in rows])) if rows else None,
        "pipeline_ms_A": round(pipeline_ms),
        "pipeline_mode": mode_label,
    }
    out_path = ROOT / "benchmarks" / "latest.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {out_path.relative_to(ROOT)} (commit it so the judge page shows it).")
    return 1 if failed else 0


def cmd_serve(args) -> int:
    import uvicorn

    print(f"Patient chat: http://localhost:{args.port}/p   Nurse: /nurse   Judges: /")
    print(f"Public link for phones: cloudflared tunnel --url http://localhost:{args.port}")
    uvicorn.run("triage.api:app", host=args.host, port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m triage.cli", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check the environment")
    d.add_argument("--live", action="store_true", help="also make one real call to each API")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("run", help="one intake")
    src = r.add_mutually_exclusive_group()
    src.add_argument("--text", help="Spanish transcript text")
    src.add_argument("--text-file", help="file containing the Spanish transcript")
    r.add_argument("--audio", help="audio file to transcribe with Whisper")
    r.add_argument("--fixture", choices=fixtures.FIXTURE_IDS, help="use a stored case (and its stored transcript)")
    r.add_argument("--mode", choices=MODES, default="auto", help="auto, offline (no API), or outage (simulate)")
    r.add_argument("--out", help="folder for the PDF and JSON (default: output/)")
    r.add_argument("--no-pdf", action="store_true")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("demo", help="the two-case demo")
    m.add_argument("--cases", nargs="+", choices=fixtures.FIXTURE_IDS, default=["A", "B"])
    m.add_argument("--mode", choices=MODES, default="auto")
    m.add_argument("--no-audio", action="store_true", help="skip speech-to-text and use the stored transcripts")
    m.add_argument("--out")
    m.set_defaults(func=cmd_demo)

    c = sub.add_parser("check-extraction", help="live Gemini vs the gold values")
    c.add_argument("--fixtures", nargs="+", choices=fixtures.FIXTURE_IDS, default=fixtures.FIXTURE_IDS)
    c.set_defaults(func=cmd_check_extraction)

    j = sub.add_parser("jev-sanity", help="live Jev sanity checks (section 9.1)")
    j.add_argument("--fixtures", nargs="+", choices=fixtures.FIXTURE_IDS, default=["A", "B", "C"])
    j.add_argument("--repeats", type=int, default=3)
    j.set_defaults(func=cmd_jev_sanity)

    e = sub.add_parser("erlang", help="queue numbers")
    e.add_argument("--arrivals", type=float, default=28.0)
    e.add_argument("--nurses", type=int, default=4)
    e.add_argument("--manual", type=float, default=8.0)
    e.add_argument("--automated", type=float, default=3.5)
    e.set_defaults(func=cmd_erlang)

    t = sub.add_parser("transcribe", help="speech-to-text only")
    t.add_argument("audio")
    t.add_argument("--fixture", choices=fixtures.FIXTURE_IDS, help="also print the word error rate against this case")
    t.set_defaults(func=cmd_transcribe)

    bn = sub.add_parser("bench", help="measure tests, speech-to-text and pipeline time; save benchmarks/latest.json")
    bn.set_defaults(func=cmd_bench)

    sv = sub.add_parser("serve", help="the web app: patient chat (/p), nurse queue (/nurse), judge page (/)")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(func=cmd_serve)

    f = sub.add_parser("prefetch", help="download the Whisper model into the project (needs internet once)")
    f.add_argument("--model", help="default: WHISPER_MODEL or 'small'")
    f.set_defaults(func=cmd_prefetch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
