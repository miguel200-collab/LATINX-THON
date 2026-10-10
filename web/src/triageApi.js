// ════════════════════════════════════════════════════════════════
// Backend API helper — all fetch requests go through API_BASE.
// Every call targets `${API_BASE}/api/...`.
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
