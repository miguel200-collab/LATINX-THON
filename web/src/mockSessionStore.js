// ════════════════════════════════════════════════════════════════
// SHARED MOCK SESSION STORE
// A submitted sample patient appears in the nurse queue
// during the same preview session. Uses a simple pub/sub pattern.
// Replace with real API calls later.
// ════════════════════════════════════════════════════════════════

import { SAMPLE_QUEUE } from './mockData.js'

const listeners = new Set()
let queue = JSON.parse(JSON.stringify(SAMPLE_QUEUE))
let audioStore = new Map() // caseId -> [{ id, blob, duration, label }]

function emit() {
  listeners.forEach((fn) => fn(queue))
}

export const sessionStore = {
  getQueue() {
    return queue
  },

  subscribe(fn) {
    listeners.add(fn)
    fn(queue)
    return () => listeners.delete(fn)
  },

  addCase(newCase) {
    queue = [newCase, ...queue]
    emit()
  },

  updateCase(id, updates) {
    queue = queue.map((c) => (c.id === id ? { ...c, ...updates } : c))
    emit()
  },

  removeCase(id) {
    queue = queue.filter((c) => c.id !== id)
    emit()
  },

  resetQueue() {
    queue = JSON.parse(JSON.stringify(SAMPLE_QUEUE))
    audioStore = new Map()
    emit()
  },

  // Audio note storage (local to preview, never uploaded)
  addAudioNote(caseId, audioNote) {
    if (!audioStore.has(caseId)) audioStore.set(caseId, [])
    audioStore.get(caseId).push(audioNote)
  },

  getAudioNotes(caseId) {
    return audioStore.get(caseId) || []
  },
}
