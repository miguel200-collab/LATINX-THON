// ════════════════════════════════════════════════════════════════
// MOCK DATA — SAMPLE VALUES, NOT MODEL OUTPUT
// This module holds all synthetic data and simulated operations.
// Replace these functions with API calls to the Python backend later.
//
// Bilingual fields (textEn, labelEn, etc.) are UI chrome only.
// Patient answers (chart.*.words) are NEVER translated — they stay
// in whatever language the patient typed them.
// ════════════════════════════════════════════════════════════════

// ── The six intake questions (SPEC section 1) ──
// `text` = Spanish (patient default), `textEn` = English
export const INTAKE_QUESTIONS = [
  { id: 1, text: 'Cuéntenos qué le pasa hoy.', textEn: 'Tell us what is happening today.' },
  { id: 2, text: '¿Dónde le duele o le molesta? ¿Se le corre a otra parte?', textEn: 'Where does it hurt or bother you? Does it spread anywhere?' },
  { id: 3, text: '¿Cuándo empezó? ¿Fue de repente o poco a poco?', textEn: 'When did it start? Was it sudden or gradual?' },
  { id: 4, text: '¿Cómo es la molestia y qué tan fuerte es, del 1 al 10?', textEn: 'What is the discomfort like and how strong is it, from 1 to 10?' },
  { id: 5, text: '¿Algo lo empeora o lo mejora?', textEn: 'Does anything make it better or worse?' },
  { id: 6, text: '¿Tiene falta de aire, mareo o desmayo, sudor frío, sangrado, o debilidad en la cara o en un brazo?', textEn: 'Do you have shortness of breath, dizziness or fainting, cold sweats, bleeding, or weakness in your face or an arm?' },
]

// ── Predefined sample answers for the "sample scenario" button ──
// Question 6 is NEVER auto-covered (SPEC requirement)
// Bilingual: patient picks the language matching their UI
export const SAMPLE_ANSWERS = {
  es: {
    1: 'Me duele mucho el pecho desde hace como una hora.',
    2: 'El dolor está en el centro del pecho y se me va al brazo izquierdo.',
    3: 'Empezó hace como una hora, de repente, mientras estaba descansando.',
    4: 'Es un dolor como un aplastamiento, muy fuerte, un 9 sobre 10.',
    5: 'El descanso no lo mejora. Me siento sudoroso y mareado.',
    // 6 intentionally omitted — never auto-covered
  },
  en: {
    1: 'I have severe chest pain that started about an hour ago.',
    2: 'The pain is in the center of my chest and radiates to my left arm.',
    3: 'It started about an hour ago, suddenly, while I was resting.',
    4: 'It is a crushing pain, very strong, a 9 out of 10.',
    5: 'Rest does not help. I feel sweaty and dizzy.',
    // 6 intentionally omitted — never auto-covered
  },
}

// ── Tier color mapping ──
// `label` = Spanish, `labelEn` = English
export const TIER_COLORS = {
  1: { bg: '#d32f2f', text: '#fff', label: 'Nivel 1 — Resucitación', labelEn: 'Level 1 — Resuscitation', light: '#ffebee' },
  2: { bg: '#ef6c00', text: '#fff', label: 'Nivel 2 — Emergencia', labelEn: 'Level 2 — Emergent', light: '#fff3e0' },
  3: { bg: '#f9a825', text: '#000', label: 'Nivel 3 — Urgente', labelEn: 'Level 3 — Urgent', light: '#fffde7' },
  4: { bg: '#2e7d32', text: '#fff', label: 'Nivel 4 — Menos urgente', labelEn: 'Level 4 — Less urgent', light: '#e8f5e9' },
  5: { bg: '#1565c0', text: '#fff', label: 'Nivel 5 — No urgente', labelEn: 'Level 5 — Non-urgent', light: '#e3f2fd' },
}

// ── Helper: get tier label for a given language ──
export function tierLabel(esi, lang) {
  const tier = TIER_COLORS[esi]
  if (!tier) return ''
  return lang === 'es' ? tier.label : tier.labelEn
}

// ── Helper: get short tier label (after the dash) ──
export function tierLabelShort(esi, lang) {
  const label = tierLabel(esi, lang)
  const parts = label.split(' — ')
  return parts[1] || label
}

// ── Synthetic nurse queue cases ──
// Every case is labeled DEMO / STORED EXAMPLE
// Patient words (chart.*.words) are always in their original Spanish.
// englishSummary is always English; spanishReadback is always Spanish.
export const SAMPLE_QUEUE = [
  {
    id: 'DEMO-001',
    label: 'STORED EXAMPLE',
    waitingMinutes: 3,
    status: 'waiting',
    suggestedTier: 1,
    redFlags: ['Dolor torácico opresivo', 'Irradiación a brazo izq.', 'Sudoración fría', 'Mareo'],
    patient: {
      age: 58, sex: 'M',
    },
    chart: {
      chiefComplaint: { extracted: 'Dolor torácico opresivo severo', words: 'Me duele mucho el pecho desde hace como una hora.' },
      location: { extracted: 'Centro de pecho, irradiación a brazo izquierdo', words: 'El dolor está en el centro del pecho y se me va al brazo izquierdo.' },
      onset: { extracted: 'Inicio súbito hace ~1 hora, en reposo', words: 'Empezó hace como una hora, de repente, mientras estaba descansando.' },
      quality: { extracted: 'Opresivo, intensidad 9/10', words: 'Es un dolor como un aplastamiento, muy fuerte, un 9 sobre 10.' },
      aggravating: { extracted: 'No mejora con el reposo', words: 'El descanso no lo mejora. Me siento sudoroso y mareado.' },
      associated: { extracted: 'Sudoración fría, mareo', words: 'Siento que me voy a desmayar y estoy sudando frío.' },
    },
    probabilities: [
      { esi: 1, probability: 0.72, expectedLoss: 2.88 },
      { esi: 2, probability: 0.18, expectedLoss: 1.80 },
      { esi: 3, probability: 0.06, expectedLoss: 0.60 },
      { esi: 4, probability: 0.03, expectedLoss: 0.30 },
      { esi: 5, probability: 0.01, expectedLoss: 0.10 },
    ],
    englishSummary: '58-year-old male presents with sudden-onset crushing chest pain (9/10) radiating to the left arm, started 1 hour ago at rest. Associated with cold sweats and dizziness. Pain not relieved by rest. High suspicion for acute coronary syndrome.',
    spanishReadback: 'Hombre de 58 años con dolor de pecho opresivo de inicio súbito, intensidad 9 sobre 10, que se irradia al brazo izquierdo. Comenzó hace una hora en reposo. Se acompaña de sudoración fría y mareo. El dolor no mejora con el reposo. Alta sospecha de síndrome coronario agudo.',
    audioNoteIds: [],
    confirmedESI: null,
    confirmedAt: null,
    reviewSeconds: null,
  },
  {
    id: 'DEMO-002',
    label: 'STORED EXAMPLE',
    waitingMinutes: 12,
    status: 'waiting',
    suggestedTier: 2,
    redFlags: ['Disnea progresiva', 'Fatiga'],
    patient: { age: 71, sex: 'F' },
    chart: {
      chiefComplaint: { extracted: 'Dificultad para respirar progresiva', words: 'Me cuesta respirar desde ayer y está empeorando.' },
      location: { extracted: 'Disnea generalizada', words: 'No es un punto específico, me cuesta respirar en general.' },
      onset: { extracted: 'Inicio gradual hace ~24 horas', words: 'Empezó ayer poco a poco, hoy está peor.' },
      quality: { extracted: 'Disnea, intensidad 6/10', words: 'Es como si no me llegara el aire, un 6 sobre 10.' },
      aggravating: { extracted: 'Empeora al acostarse', words: 'Cuando me acuesto me cuesta más respirar.' },
      associated: { extracted: 'Fatiga, sin dolor torácico', words: 'Me siento muy cansada pero no me duele el pecho.' },
    },
    probabilities: [
      { esi: 1, probability: 0.05, expectedLoss: 0.50 },
      { esi: 2, probability: 0.55, expectedLoss: 5.50 },
      { esi: 3, probability: 0.25, expectedLoss: 2.50 },
      { esi: 4, probability: 0.10, expectedLoss: 1.00 },
      { esi: 5, probability: 0.05, expectedLoss: 0.50 },
    ],
    englishSummary: '71-year-old female with progressive dyspnea over 24 hours, worse when supine. Severity 6/10. Associated fatigue, no chest pain. Consider CHF exacerbation.',
    spanishReadback: 'Mujer de 71 años con dificultad para respirar progresiva en 24 horas, que empeora al acostarse. Intensidad 6 sobre 10. Se acompaña de fatiga, sin dolor de pecho. Considerar exacerbación de insuficiencia cardíaca.',
    audioNoteIds: [],
    confirmedESI: null,
    confirmedAt: null,
    reviewSeconds: null,
  },
  {
    id: 'DEMO-003',
    label: 'STORED EXAMPLE',
    waitingMinutes: 27,
    status: 'waiting',
    suggestedTier: 3,
    redFlags: ['Dolor abdominal difuso'],
    patient: { age: 34, sex: 'F' },
    chart: {
      chiefComplaint: { extracted: 'Dolor abdominal', words: 'Me duele la barriga desde anoche.' },
      location: { extracted: 'Abdomen inferior, sin irradiación', words: 'Me duele abajo de la barriga, no se va a otra parte.' },
      onset: { extracted: 'Inicio gradual anoche', words: 'Anoche empezó poco a poco.' },
      quality: { extracted: 'Cólico, intensidad 5/10', words: 'Es como un retortijón, un 5 sobre 10.' },
      aggravating: { extracted: 'Empeora al comer', words: 'Cuando como me duele más.' },
      associated: { extracted: 'Náuseas, sin fiebre', words: 'Tengo ganas de vomitar pero no tengo fiebre.' },
    },
    probabilities: [
      { esi: 1, probability: 0.02, expectedLoss: 0.20 },
      { esi: 2, probability: 0.08, expectedLoss: 0.80 },
      { esi: 3, probability: 0.52, expectedLoss: 5.20 },
      { esi: 4, probability: 0.28, expectedLoss: 2.80 },
      { esi: 5, probability: 0.10, expectedLoss: 1.00 },
    ],
    englishSummary: '34-year-old female with gradual-onset lower abdominal pain since last night, cramping quality (5/10), worse with eating. Associated nausea, no fever.',
    spanishReadback: 'Mujer de 34 años con dolor abdominal inferior de inicio gradual desde anoche, tipo cólico (5 sobre 10), que empeora al comer. Se acompaña de náuseas, sin fiebre.',
    audioNoteIds: [],
    confirmedESI: null,
    confirmedAt: null,
    reviewSeconds: null,
  },
  {
    id: 'DEMO-004',
    label: 'STORED EXAMPLE',
    waitingMinutes: 45,
    status: 'waiting',
    suggestedTier: 4,
    redFlags: [],
    patient: { age: 22, sex: 'M' },
    chart: {
      chiefComplaint: { extracted: 'Tobillo hinchado después de torcedura', words: 'Me torcí el tobillo jugando y se me hinchó.' },
      location: { extracted: 'Tobillo derecho', words: 'El tobillo derecho me duele mucho.' },
      onset: { extracted: 'Inicio hace 2 horas durante deporte', words: 'Hace como dos horas, jugando fútbol.' },
      quality: { extracted: 'Dolor punzante, intensidad 4/10', words: 'Me duele como punzadas, un 4 sobre 10.' },
      aggravating: { extracted: 'Empeora al caminar', words: 'Cuando camino me duele más.' },
      associated: { extracted: 'Sin otros síntomas', words: 'No tengo nada más, solo el tobillo.' },
    },
    probabilities: [
      { esi: 1, probability: 0.01, expectedLoss: 0.10 },
      { esi: 2, probability: 0.03, expectedLoss: 0.30 },
      { esi: 3, probability: 0.12, expectedLoss: 1.20 },
      { esi: 4, probability: 0.62, expectedLoss: 6.20 },
      { esi: 5, probability: 0.22, expectedLoss: 2.20 },
    ],
    englishSummary: '22-year-old male with right ankle sprain 2 hours ago during soccer. Sharp pain (4/10), worse with walking. No other symptoms.',
    spanishReadback: 'Hombre de 22 años con esguince de tobillo derecho hace 2 horas jugando fútbol. Dolor punzante (4 sobre 10), que empeora al caminar. Sin otros síntomas.',
    audioNoteIds: [],
    confirmedESI: null,
    confirmedAt: null,
    reviewSeconds: null,
  },
  {
    id: 'DEMO-005',
    label: 'STORED EXAMPLE',
    waitingMinutes: 68,
    status: 'confirmed',
    suggestedTier: 5,
    redFlags: [],
    patient: { age: 45, sex: 'F' },
    chart: {
      chiefComplaint: { extracted: 'Tos persistente', words: 'Tengo tos desde hace tres días.' },
      location: { extracted: 'Tos seca, sin dolor localizado', words: 'No me duele nada específico, solo toso.' },
      onset: { extracted: 'Inicio gradual hace 3 días', words: 'Empezó hace tres días, poco a poco.' },
      quality: { extracted: 'Tos seca, intensidad 2/10', words: 'Es una tos seca, un 2 sobre 10.' },
      aggravating: { extracted: 'Empeora de noche', words: 'De noche toso más.' },
      associated: { extracted: 'Sin fiebre, sin falta de aire', words: 'No tengo fiebre ni me cuesta respirar.' },
    },
    probabilities: [
      { esi: 1, probability: 0.01, expectedLoss: 0.10 },
      { esi: 2, probability: 0.02, expectedLoss: 0.20 },
      { esi: 3, probability: 0.07, expectedLoss: 0.70 },
      { esi: 4, probability: 0.20, expectedLoss: 2.00 },
      { esi: 5, probability: 0.70, expectedLoss: 7.00 },
    ],
    englishSummary: '45-year-old female with dry cough for 3 days, gradual onset, worse at night. No fever, no dyspnea. Likely viral URI.',
    spanishReadback: 'Mujer de 45 años con tos seca de 3 días de evolución, inicio gradual, que empeora de noche. Sin fiebre ni dificultad para respirar. Probable infección viral.',
    audioNoteIds: [],
    confirmedESI: 5,
    confirmedAt: '2026-10-10T11:45:00',
    reviewSeconds: 42,
  },
]

// ── Chart field definitions for the nurse table ──
// `label` = Spanish, `labelEn` = English
export const CHART_FIELDS = [
  { key: 'chiefComplaint', label: 'Motivo principal', labelEn: 'Chief complaint' },
  { key: 'location', label: 'Localización', labelEn: 'Location' },
  { key: 'onset', label: 'Inicio', labelEn: 'Onset' },
  { key: 'quality', label: 'Calidad / Intensidad', labelEn: 'Quality / Intensity' },
  { key: 'aggravating', label: 'Agravantes / Atenuantes', labelEn: 'Aggravating / Relieving' },
  { key: 'associated', label: 'Síntomas asociados', labelEn: 'Associated symptoms' },
]

// ── Helper: get chart field label for a given language ──
export function fieldLabel(field, lang) {
  return lang === 'es' ? field.label : field.labelEn
}

// ── Simulated operations (replace with API calls later) ──
// These return Promises to mimic network latency.

export function simulateSendToNurse(patientData) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        ...patientData,
        id: 'DEMO-' + Date.now().toString().slice(-6),
        label: 'DEMO',
        waitingMinutes: 0,
        status: 'waiting',
        suggestedTier: patientData.suggestedTier || 3,
        redFlags: patientData.redFlags || [],
        patient: { age: patientData.age || 45, sex: patientData.sex || 'X' },
        chart: patientData.chart || {},
        probabilities: patientData.probabilities || SAMPLE_QUEUE[2].probabilities,
        englishSummary: patientData.englishSummary || 'Sample summary — not model output.',
        spanishReadback: patientData.spanishReadback || 'Resumen de muestra — no es salida del modelo.',
        audioNoteIds: patientData.audioNoteIds || [],
        confirmedESI: null,
        confirmedAt: null,
        reviewSeconds: null,
      })
    }, 1200)
  })
}

export function simulateConfirmESI(caseId, esi) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ success: true, caseId, esi, confirmedAt: new Date().toISOString() })
    }, 800)
  })
}

// ── Simulated error states for preview (bilingual) ──
// Keys match the error type strings returned by useVoiceRecorder.
export const SIMULATED_ERRORS = {
  es: {
    permissionDenied: {
      title: 'Permiso de micrófono denegado',
      message: 'No se pudo acceder al micrófono. Puede continuar escribiendo sus respuestas.',
    },
    noMicrophone: {
      title: 'No se encontró micrófono',
      message: 'No hay micrófono disponible en este dispositivo. Puede continuar escribiendo.',
    },
    unsupported: {
      title: 'Navegador no compatible',
      message: 'La grabación de audio no es compatible con este navegador. Puede continuar escribiendo.',
    },
    tooShort: {
      title: 'Nota de voz muy corta',
      message: 'La grabación duró menos de 0.7s. Intente de nuevo.',
    },
    saveError: {
      title: 'Error de guardado (escenario de demostración)',
      message: 'No se pudo enviar la respuesta al personal de enfermería. Este es un escenario de demostración.',
    },
  },
  en: {
    permissionDenied: {
      title: 'Microphone permission denied',
      message: 'Could not access the microphone. You can continue typing your answers.',
    },
    noMicrophone: {
      title: 'No microphone found',
      message: 'No microphone available on this device. You can continue typing.',
    },
    unsupported: {
      title: 'Unsupported browser',
      message: 'Audio recording is not supported in this browser. You can continue typing.',
    },
    tooShort: {
      title: 'Voice note too short',
      message: 'The recording was shorter than 0.7s. Please try again.',
    },
    saveError: {
      title: 'Save error (demo scenario)',
      message: 'Could not send the answer to the nursing staff. This is a demo scenario.',
    },
  },
}
