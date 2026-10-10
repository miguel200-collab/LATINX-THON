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
    : DEFAULT_TUNNEL)

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
