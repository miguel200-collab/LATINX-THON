# Backend Build Log

| Time | Prompt | Result | Errors and fixes |
|---|---|---|---|
| 2026-10-10 11:50 | P0 | Project skeleton created, 80 packages synced, core imports verified | Sandbox network DNS on uv sync; resolved with network approval |
| 2026-10-10 12:12 | P1 | 61 passed in 0.49s; 4 non-empty synthetic WAV clips generated | Added pythonpath to pyproject.toml; imported triage.config before monkeypatch in conftest.py |
| 2026-10-10 12:22 | P2 | 102 passed in 0.76s; Gemini extraction, Jev Choice client, regex safety hold, and key masking verified | None |
| 2026-10-10 12:35 | P3 | 142 passed; Whisper model cached; CLI demo runs Case A (suggested ESI 2) & Case B (ESI 4); single-page PDF verified | None |
| 2026-10-10 12:41 | P4 | 181 passed in 24.43s; all FastAPI endpoints, coverage guards, readback templates, sessions, and web views verified | None |
| 2026-10-10 12:52 | P5 | Server live on :8000; Cloudflare tunnel active at https://saves-brandon-hundreds-charms.trycloudflare.com; base44/README.md updated | None |
| 2026-10-10 13:40 | P6 | Benchmarks: 181 tests passed; median ASR 2.4s (WER 0.0%-6.1%); pipeline 2.4s; benchmarks/latest.json saved | None |
| 2026-10-10 14:21 | P7 | 181 passed in 12.23s; tunnel URL updated in base44/README.md; dynamic origin routing enabled | None |
| 2026-10-10 15:48 | P8: Live keys verified & Gemini live | 181 passed in 13.01s; Gemini timeout set to 12s to meet SDK min deadline; doctor --live tested | Gemini min deadline 10s enforced |
| 2026-10-10 16:08 | P9: Live acuity scoring fallback & judge flow diagnosis | 183 passed in 14.15s; Gemini acuity scoring fallback added to score() for novel voice cases; schemas updated | Novel cases defaulted to ESI 2 safety hold due to TypeSafe key rejection; added Gemini acuity evaluation on structured symptoms |
| 2026-10-10 16:27 | P10: Model fallback error handling & timeout | 183 passed in 15.82s; fallback broadened in _gemini_call to catch 504 DEADLINE_EXCEEDED; gemini_timeout_s increased to 15s | 504 DEADLINE_EXCEEDED was not caught by 503-only check, causing extraction to bypass gemini-2.5-flash fallback and drop into regex_hold; fixed by continuing to fallback model |

