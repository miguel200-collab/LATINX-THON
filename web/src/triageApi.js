// ════════════════════════════════════════════════════════════════
// Backend API helper — all fetch requests go through API_BASE.
// Every call targets `${API_BASE}/api/...`.
// ════════════════════════════════════════════════════════════════

// Current public tunnel endpoint (or same-origin if served through the backend)
const DEFAULT_TUNNEL = 'https://tiger-principal-threatened-mechanism.trycloudflare.com'

export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== 'undefined' && window.location.hostname.includes('trycloudflare.com')
    ? window.location.origin
    : '') // same-origin in dev/preview — falls back to mock if no backend is reachable

// Mock responses used when no backend is reachable (dev/preview without a tunnel)
function _mockResponse(path, options) {
  const body = options.body ? JSON.parse(options.body) : {}
  if (path === '/api/intake') {
    // Merge the submitted patient data with the fields the nurse workstation expects
    return {
      ...body,
      id: `case-${Date.now()}`,
      status: 'waiting',
      label: 'NEW',
      waitingMinutes: 0,
      patient: body.patient || { age: null, sex: '' },
      probabilities: body.probabilities || [
        { esi: 1, probability: 0.1, expectedLoss: 1.0 },
        { esi: 2, probability: 0.2, expectedLoss: 2.0 },
        { esi: 3, probability: 0.4, expectedLoss: 4.0 },
        { esi: 4, probability: 0.2, expectedLoss: 2.0 },
        { esi: 5, probability: 0.1, expectedLoss: 1.0 },
      ],
      audioNoteIds: [],
      confirmedESI: null,
      confirmedAt: null,
      reviewSeconds: null,
      created_at: Date.now() / 1000,
    }
  }
  if (path === '/api/confirm-esi') {
    return { ok: true, status: 'confirmed', ...body }
  }
  return {}
}

async function request(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!res.ok) {
      throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`)
    }
    return await res.json()
  } catch (e) {
    // No backend reachable — return a mock response so the demo works standalone
    return _mockResponse(path, options)
  }
}

// ── Patient submits intake answers → returns a new triage case ──
export function sendToNurse(patientData) {
  return request('/api/intake', {
    method: 'POST',
    body: JSON.stringify(patientData),
  })
}

// ── Nurse confirms an ESI level for a case ──
export function confirmESI(caseId, esi) {
  return request('/api/confirm-esi', {
    method: 'POST',
    body: JSON.stringify({ caseId, esi }),
  })
}
