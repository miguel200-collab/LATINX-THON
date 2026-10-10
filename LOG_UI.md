# UI Build Log

| Time | Prompt | Result | Errors and fixes |
|---|---|---|---|
| 2026-10-10 12:15 | Frontend preview build | Vite+React frontend in web/: Patient (WhatsApp) + Nurse (Win7 EHR) pages, mock data, shared session store, voice recording, ESI confirmation flow. All interactions verified in preview. | None |
| 2026-10-10 14:21 | P7: Publish & deployment config | Fixed API_BASE in web/src/triageApi.js to dynamically bind active tunnel & same-origin; rebuilt bundle web/dist/ | Hardcoded stale tunnel URL resolved |
| 2026-10-10 15:27 | Base44 hybrid connection | Full backend wiring: real audio to /api/sessions/answers, live queue polling /api/queue, PDF download, and graceful offline fallback | None |
