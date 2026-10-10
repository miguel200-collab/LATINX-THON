// ════════════════════════════════════════════════════════════════
// Backend API helper — all fetch requests go through API_BASE.
// Every call targets `${API_BASE}/api/...`.
// When the backend is not connected, calls fall back to a local
// case so the nurse queue still updates during the preview phase.
// ════════════════════════════════════════════════════════════════

export const API_BASE = 'https://saves-brandon-hundreds-charms.trycloudflare.com'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

// ── Local fallback: create a case from patient answers ──
// No AI extraction, probabilities, or clinical scoring — just the
// patient's raw answers so the nurse can review them.
function createLocalCase(patientData) {
  return {
    id: 'INTAKE-' + Date.now().toString().slice(-6),
    label: 'NEW',
    waitingMinutes: 0,
    status: 'waiting',
    suggestedTier: null,
    redFlags: [],
    patient: { age: null, sex: null },
    chart: patientData.chart || {},
    probabilities: [],
    englishSummary: '',
    spanishReadback: '',
    audioNoteIds: patientData.audioNoteIds || [],
    confirmedESI: null,
    confirmedAt: null,
    reviewSeconds: null,
    submittedAt: new Date().toISOString(),
  }
}

// ── Patient submits intake answers → returns a new triage case ──
export async function sendToNurse(patientData) {
  try {
    return await request('/api/intake', {
      method: 'POST',
      body: JSON.stringify(patientData),
    })
  } catch (e) {
    // Backend not connected — fall back to a local case so the
    // nurse queue updates during the preview phase.
    return createLocalCase(patientData)
  }
}

// ── Nurse confirms an ESI level for a case ──
export async function confirmESI(caseId, esi) {
  try {
    return await request('/api/confirm-esi', {
      method: 'POST',
      body: JSON.stringify({ caseId, esi }),
    })
  } catch (e) {
    // Backend not connected — return a local confirmation.
    return { success: true, caseId, esi, confirmedAt: new Date().toISOString() }
  }
}
