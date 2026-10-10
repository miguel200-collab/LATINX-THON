// ════════════════════════════════════════════════════════════════
// Backend API helper — all fetch requests go through API_BASE.
// Connects Base44 React frontend with the live Python engine.
// ════════════════════════════════════════════════════════════════

const DEFAULT_TUNNEL = 'https://tiger-principal-threatened-mechanism.trycloudflare.com'

export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== 'undefined' && window.location.hostname.includes('trycloudflare.com')
    ? window.location.origin
    : DEFAULT_TUNNEL)

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 15000)
  try {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    const res = await fetch(url, {
      signal: controller.signal,
      ...options,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(options.headers || {}),
      },
    })
    if (!res.ok) {
      throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`)
    }
    return await res.json()
  } finally {
    clearTimeout(timeoutId)
  }
}

// ── Check backend health & live AI status ──
export async function checkBackendHealth() {
  try {
    const data = await request('/api/health', { timeout: 3500 })
    return { ok: true, data }
  } catch (err) {
    return { ok: false, error: err.message }
  }
}

// ── Create a live intake session ──
export async function createSession() {
  return request('/api/sessions', { method: 'POST' })
}

// ── Submit a patient answer (voice or text) ──
export async function submitAnswer(sid, qid, { text, audioBlob } = {}) {
  if (audioBlob) {
    const formData = new FormData()
    formData.append('question_id', qid)
    formData.append('audio', audioBlob, `${qid}.webm`)
    if (text) formData.append('text', text)
    return request(`/api/sessions/${sid}/answers`, {
      method: 'POST',
      body: formData,
      timeout: 30000,
    })
  } else {
    return request(`/api/sessions/${sid}/answers`, {
      method: 'POST',
      body: JSON.stringify({ question_id: qid, text: text || '' }),
    })
  }
}

// ── Submit intake (runs Whisper -> Gemini -> Jev -> Loss -> PDF) ──
export async function submitSession(sid) {
  return request(`/api/sessions/${sid}/submit`, { method: 'POST', timeout: 25000 })
}

// ── Fetch nurse queue from backend ──
export async function fetchQueue() {
  return request('/api/queue', { timeout: 6000 })
}

// ── Fetch detailed session ──
export async function fetchSessionDetail(sid) {
  return request(`/api/sessions/${sid}`, { timeout: 6000 })
}

// ── Nurse confirms official ESI level ──
export async function confirmESI(sid, esi, readbackSeconds = 0, fields = {}) {
  if (!sid || sid.startsWith('DEMO-') || !sid.startsWith('s-')) {
    return request('/api/confirm-esi', {
      method: 'POST',
      body: JSON.stringify({ caseId: sid, esi }),
    })
  }
  return request(`/api/sessions/${sid}/confirm`, {
    method: 'POST',
    body: JSON.stringify({
      official_esi: esi,
      readback_seconds: readbackSeconds,
      fields,
    }),
  })
}

// ── Legacy / quick mock intake helper ──
export function sendToNurse(patientData) {
  return request('/api/intake', {
    method: 'POST',
    body: JSON.stringify(patientData),
  })
}

// ── Map a backend session detail to NursePage case format ──
export function mapBackendSessionToCase(detail) {
  const r = detail.result || {}
  const chart = r.extraction?.chart || {}
  const flag = r.flag || {}
  const probabilities = flag.probabilities || {}
  const losses = flag.losses || {}
  const waitSec = detail.summary?.wait_seconds || Math.round(Date.now() / 1000 - (detail.submitted_at || detail.created_at || Date.now() / 1000))

  return {
    id: detail.id,
    label: detail.fixture_id ? `SAMPLE ${detail.fixture_id}` : 'LIVE INTAKE',
    waitingMinutes: Math.max(1, Math.round(waitSec / 60)),
    status: detail.status || 'waiting',
    suggestedTier: flag.suggested_review_tier || 3,
    redFlags: chart.red_flag_symptoms || [],
    patient: {
      age: 52,
      sex: '—',
    },
    chart: {
      chiefComplaint: {
        extracted: chart.chief_complaint || 'En evaluación clínica',
        words: detail.answers?.[0]?.text || '',
      },
      location: {
        extracted: chart.location || 'No especificado',
        words: detail.answers?.[1]?.text || '',
      },
      onset: {
        extracted: chart.onset || 'No especificado',
        words: detail.answers?.[2]?.text || '',
      },
      quality: {
        extracted: chart.quality || 'No especificado',
        words: detail.answers?.[3]?.text || '',
      },
      aggravating: {
        extracted: chart.aggravating_or_alleviating || 'No especificado',
        words: detail.answers?.[4]?.text || '',
      },
      associated: {
        extracted: Array.isArray(chart.associated_symptoms) ? chart.associated_symptoms.join(', ') : 'Ninguno',
        words: detail.answers?.[5]?.text || '',
      },
    },
    probabilities: [1, 2, 3, 4, 5].map((esi) => ({
      esi,
      probability: probabilities[String(esi)] ?? probabilities[esi] ?? 0.2,
      expectedLoss: losses[String(esi)] ?? losses[esi] ?? 1.0,
    })),
    englishSummary: r.labels?.headline || 'Patient clinical intake in progress.',
    spanishReadback: detail.readback_es || r.labels?.headline || 'Lectura de enfermería en progreso.',
    audioNotes: (detail.answers || [])
      .filter((a) => a.audio_file)
      .map((a, i) => ({
        id: `audio-${i}`,
        url: `${API_BASE}/api/sessions/${detail.id}/audio/${a.audio_file}`,
        duration: Math.round((a.asr_ms || 2000) / 100) / 10,
      })),
    pdfUrl: `${API_BASE}/api/sessions/${detail.id}/pdf`,
    confirmedESI: detail.confirmation?.official_esi || detail.official_esi || null,
    confirmedAt: detail.confirmation?.confirmed_at || detail.confirmed_at || null,
    reviewSeconds: detail.confirmation?.readback_seconds || null,
  }
}
