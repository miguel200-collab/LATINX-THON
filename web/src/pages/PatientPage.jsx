import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder.js'
import { INTAKE_QUESTIONS, SAMPLE_ANSWERS, SIMULATED_ERRORS } from '../mockData.js'
import { sendToNurse } from '../triageApi.js'
import { sessionStore } from '../mockSessionStore.js'
import { makeT } from '../i18n.js'
import LanguageToggle from '../components/LanguageToggle.jsx'
import ProgressDots from '../components/patient/ProgressDots.jsx'
import VoiceNotePlayer from '../components/patient/VoiceNotePlayer.jsx'
import RecordingBar from '../components/patient/RecordingBar.jsx'
import '../styles/patient.css'

let msgId = 0
const nextId = () => ++msgId

const formatTimestamp = () => {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

export default function PatientPage() {
  const [lang, setLang] = useState('es') // Patient defaults to Spanish
  const [messages, setMessages] = useState([])
  const [currentQ, setCurrentQ] = useState(-1) // -1 = intro, 0-5 = questions, 6 = done
  const [inputText, setInputText] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [answered, setAnswered] = useState([false, false, false, false, false, false])
  const [showSaveError, setShowSaveError] = useState(false)
  const [showPermissionError, setShowPermissionError] = useState(false)
  const messagesEndRef = useRef(null)
  const holdTimerRef = useRef(null)
  const holdStartedRef = useRef(false)
  const pointerStartRef = useRef({ x: 0, y: 0 })
  const slideHandledRef = useRef(false)

  const t = makeT(lang, 'patient')
  const sampleAns = SAMPLE_ANSWERS[lang]
  const qText = (i) => lang === 'es' ? INTAKE_QUESTIONS[i].text : INTAKE_QUESTIONS[i].textEn
  const errs = SIMULATED_ERRORS[lang]

  const {
    isRecording, isLocked, seconds, error, hasSupport,
    startRecording, stopRecording, cancelRecording, lockRecording, clearError,
  } = useVoiceRecorder()

  // Translate the error type code from the hook into { title, message }
  const errorInfo = error ? errs[error] : null

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  // ── Start intake ──
  const startIntake = useCallback(() => {
    setMessages([{
      id: nextId(), type: 'question', questionId: 1,
      text: qText(0), timestamp: formatTimestamp(),
    }])
    setAnswered([false, false, false, false, false, false])
    setShowSaveError(false)
    setCurrentQ(0)
  }, [lang])

  // ── Advance to next question ──
  const advanceToNext = useCallback((qIndex) => {
    const nextIndex = qIndex + 1
    if (nextIndex >= 6) {
      setCurrentQ(6)
      setMessages((prev) => [...prev, {
        id: nextId(), type: 'completion', timestamp: formatTimestamp(),
      }])
      return
    }
    setCurrentQ(nextIndex)
    setMessages((prev) => [...prev, {
      id: nextId(), type: 'question', questionId: nextIndex + 1,
      text: qText(nextIndex), timestamp: formatTimestamp(),
    }])
  }, [lang])

  // ── Submit an answer ──
  const submitAnswer = useCallback(async (text, audioNote = null) => {
    if (currentQ < 0 || currentQ >= 6 || isSending) return
    if (!text && !audioNote) return

    const qIndex = currentQ
    setMessages((prev) => [...prev, {
      id: nextId(), type: 'answer', questionId: qIndex + 1,
      text: text || '', audioNote, timestamp: formatTimestamp(),
    }])
    setInputText('')
    setIsSending(true)

    // Simulate sending to nurse queue
    try {
      const patientData = buildPatientData(messages, text, qIndex)
      const newCase = await sendToNurse(patientData)
      sessionStore.addCase(newCase)
    } catch (e) { /* demo — won't fail */ }

    await new Promise((r) => setTimeout(r, 1200))
    setIsSending(false)
    setAnswered((prev) => { const n = [...prev]; n[qIndex] = true; return n })

    setMessages((prev) => [...prev, {
      id: nextId(), type: 'check', questionId: qIndex + 1, timestamp: formatTimestamp(),
    }])

    advanceToNext(qIndex)
  }, [currentQ, isSending, messages, advanceToNext])

  // ── Sample scenario: auto-cover Q1-Q5, require Q6 ──
  const startSampleScenario = useCallback(() => {
    const msgs = []
    // Q1 with sample answer
    msgs.push({ id: nextId(), type: 'question', questionId: 1, text: qText(0), timestamp: formatTimestamp() })
    msgs.push({ id: nextId(), type: 'answer', questionId: 1, text: sampleAns[1], timestamp: formatTimestamp() })
    msgs.push({ id: nextId(), type: 'check', questionId: 1, timestamp: formatTimestamp() })
    // Q2-Q5 auto-covered
    for (let i = 1; i <= 4; i++) {
      msgs.push({ id: nextId(), type: 'question', questionId: i + 1, text: qText(i), timestamp: formatTimestamp() })
      msgs.push({ id: nextId(), type: 'autoCovered', questionId: i + 1, timestamp: formatTimestamp() })
      msgs.push({ id: nextId(), type: 'check', questionId: i + 1, timestamp: formatTimestamp() })
    }
    // Q6 — NOT auto-covered
    msgs.push({ id: nextId(), type: 'question', questionId: 6, text: qText(5), timestamp: formatTimestamp() })

    setMessages(msgs)
    setAnswered([true, true, true, true, true, false])
    setCurrentQ(5)

    // Send scenario patient to nurse queue
    sendToNurse(buildScenarioData(lang)).then((c) => sessionStore.addCase(c))
  }, [lang])

  // ── Voice recording: mic button handlers ──
  const handleMicPointerDown = useCallback((e) => {
    if (currentQ < 0 || currentQ >= 6 || isSending || isRecording) return
    e.preventDefault()
    pointerStartRef.current = { x: e.clientX, y: e.clientY }
    holdStartedRef.current = false
    slideHandledRef.current = false
    holdTimerRef.current = setTimeout(async () => {
      holdStartedRef.current = true
      await startRecording()
    }, 280)
  }, [currentQ, isSending, isRecording, startRecording])

  const handleMicPointerMove = useCallback((e) => {
    if (!holdStartedRef.current || slideHandledRef.current || !isRecording) return
    const dx = e.clientX - pointerStartRef.current.x
    const dy = e.clientY - pointerStartRef.current.y
    if (dy < -50) { lockRecording(); slideHandledRef.current = true }
    else if (dx < -50) { cancelRecording(); slideHandledRef.current = true }
  }, [isRecording, lockRecording, cancelRecording])

  const handleMicPointerUp = useCallback(async (e) => {
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current)
    if (!holdStartedRef.current) return // let click handler deal with tap mode
    if (slideHandledRef.current) return // already handled by slide
    if (isRecording && !isLocked) {
      const result = await stopRecording()
      if (result) submitAnswer('', result)
    }
  }, [isRecording, isLocked, stopRecording, submitAnswer])

  const handleMicClick = useCallback(async () => {
    // Only handle tap mode (not hold)
    if (holdStartedRef.current) { holdStartedRef.current = false; return }
    if (currentQ < 0 || currentQ >= 6 || isSending) return
    if (isRecording && !isLocked) {
      // Tap mode: stop and send
      const result = await stopRecording()
      if (result) submitAnswer('', result)
    } else if (!isRecording) {
      // Tap mode: start recording
      await startRecording()
    }
  }, [currentQ, isSending, isRecording, isLocked, startRecording, stopRecording, submitAnswer])

  const handleStopFromBar = useCallback(async () => {
    const result = await stopRecording()
    if (result) submitAnswer('', result)
  }, [stopRecording, submitAnswer])

  // ── Text submit ──
  const handleTextSubmit = useCallback(() => {
    if (!inputText.trim() || isSending) return
    submitAnswer(inputText.trim())
  }, [inputText, isSending, submitAnswer])

  // ── Use sample answer ──
  const useSampleAnswer = useCallback(() => {
    if (currentQ < 0 || currentQ >= 6) return
    const sample = sampleAns[currentQ + 1]
    if (sample) submitAnswer(sample)
  }, [currentQ, submitAnswer, sampleAns])

  // ── Simulated save error preview ──
  const triggerSaveError = useCallback(() => {
    startIntake()
    setTimeout(() => { setIsSending(true); setTimeout(() => { setIsSending(false); setShowSaveError(true) }, 800) }, 300)
  }, [startIntake])

  const isIntro = currentQ === -1
  const isDone = currentQ === 6
  const canInput = currentQ >= 0 && currentQ < 6 && !isSending

  return (
    <div className="patient-page">
      {/* Header */}
      <div className="patient-header">
        <div className="patient-header__avatar">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="rgba(255,255,255,0.9)">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z" />
          </svg>
        </div>
        <div className="patient-header__info">
          <div className="patient-header__title">{t('headerTitle')}</div>
          <div className="patient-header__subtitle">{t('headerSubtitle')}</div>
        </div>
        <LanguageToggle lang={lang} setLang={setLang} variant="light" />
        <div className="patient-header__demo-tag">DEMO</div>
      </div>

      {/* Progress dots */}
      {currentQ >= 0 && currentQ < 6 && (
        <div className="patient-progress">
          <ProgressDots current={currentQ} total={6} answered={answered} lang={lang} />
        </div>
      )}

      {/* Chat area */}
      <div className="patient-chat">
        {isIntro && (
          <div className="patient-intro">
            <div className="patient-intro__card">
              <h2>{t('introTitle')}</h2>
              <p>{t('introBody')}</p>
              <div className="patient-intro__buttons">
                <button className="patient-intro__btn patient-intro__btn--primary" onClick={startIntake}>
                  {t('startBtn')}
                </button>
                <button className="patient-intro__btn patient-intro__btn--secondary" onClick={startSampleScenario}>
                  {t('sampleBtn')}
                </button>
              </div>
              <div className="patient-intro__preview-toggles">
                <button className="patient-intro__preview-btn" onClick={() => setShowPermissionError(true)}>
                  {t('previewPermission')}
                </button>
                <button className="patient-intro__preview-btn" onClick={triggerSaveError}>
                  {t('previewSaveError')}
                </button>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.type === 'question') {
            // Look up question text dynamically so it re-renders in the
            // current language when the toggle changes. The patient's
            // answers (below) are NOT re-translated — they stay original.
            const qIdx = msg.questionId - 1
            const qTextValue = qIdx >= 0 && qIdx < INTAKE_QUESTIONS.length
              ? qText(qIdx)
              : msg.text
            return (
              <div key={msg.id} className="chat-bubble chat-bubble--question">
                <div className="chat-bubble__text">{qTextValue}</div>
                <div className="chat-bubble__time">{msg.timestamp}</div>
              </div>
            )
          }
          if (msg.type === 'answer') {
            return (
              <div key={msg.id} className="chat-bubble chat-bubble--answer">
                {msg.audioNote ? (
                  <VoiceNotePlayer url={msg.audioNote.url} duration={msg.audioNote.duration} isOwn timestamp={msg.timestamp} lang={lang} />
                ) : (
                  <>
                    <div className="chat-bubble__text">{msg.text}</div>
                    <div className="chat-bubble__time">{msg.timestamp}</div>
                  </>
                )}
              </div>
            )
          }
          if (msg.type === 'autoCovered') {
            return (
              <div key={msg.id} className="chat-auto-covered">
                <div className="chat-auto-covered__icon">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>{t('autoCovered')}</span>
              </div>
            )
          }
          if (msg.type === 'check') {
            return (
              <div key={msg.id} className="chat-check">
                <div className="chat-check__icon">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3">
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>{t('answerRegistered')}</span>
              </div>
            )
          }
          if (msg.type === 'completion') {
            return (
              <div key={msg.id} className="chat-completion">
                <div className="chat-completion__icon">
                  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="#008069" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M8 12l3 3 5-6" />
                  </svg>
                </div>
                <p className="chat-completion__text">
                  {t('completionText')}
                </p>
                <button className="chat-completion__btn" onClick={startIntake}>
                  {t('restartBtn')}
                </button>
              </div>
            )
          }
          return null
        })}

        {isSending && (
          <div className="chat-sending">
            <div className="chat-sending__dots"><span></span><span></span><span></span></div>
            <span>{t('sending')}</span>
          </div>
        )}

        {showSaveError && (
          <div className="chat-error-preview">
            <div className="chat-error-preview__icon">⚠</div>
            <div>
              <div className="chat-error-preview__title">{errs.saveError.title}</div>
              <div className="chat-error-preview__msg">{errs.saveError.message}</div>
            </div>
            <button className="chat-error-preview__close" onClick={() => setShowSaveError(false)}>×</button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Permission error preview overlay */}
      {showPermissionError && (
        <div className="patient-error-overlay" onClick={() => setShowPermissionError(false)}>
          <div className="patient-error-overlay__card" onClick={(e) => e.stopPropagation()}>
            <div className="patient-error-overlay__icon">🎤</div>
            <div className="patient-error-overlay__title">{errs.permissionDenied.title}</div>
            <div className="patient-error-overlay__msg">{errs.permissionDenied.message}</div>
            <div className="patient-error-overlay__hint">{t('demoErrorHint')}</div>
            <button className="patient-error-overlay__btn" onClick={() => setShowPermissionError(false)}>
              {t('understood')}
            </button>
          </div>
        </div>
      )}

      {/* Real recording error toast */}
      {errorInfo && (
        <div className="patient-error-toast">
          <div className="patient-error-toast__icon">⚠</div>
          <div>
            <div className="patient-error-toast__title">{errorInfo.title}</div>
            <div className="patient-error-toast__msg">{errorInfo.message}</div>
          </div>
          <button className="patient-error-toast__close" onClick={clearError}>×</button>
        </div>
      )}

      {/* Recording bar */}
      {isRecording && (
        <RecordingBar
          seconds={seconds}
          isLocked={isLocked}
          onStop={handleStopFromBar}
          onCancel={cancelRecording}
          lang={lang}
        />
      )}

      {/* Composer */}
      {canInput && !isRecording && (
        <div className="patient-composer">
          {INTAKE_QUESTIONS[currentQ] && sampleAns[currentQ + 1] && (
            <button
              className="patient-composer__sample"
              onClick={useSampleAnswer}
              title={t('sampleAria')}
              aria-label={t('sampleAria')}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L9 9H2l5.5 4.5L5 21l7-5 7 5-2.5-7.5L22 9h-7z" />
              </svg>
              <span>{t('sampleLabel')}</span>
            </button>
          )}
          <div className="patient-composer__input-wrap">
            <input
              type="text"
              className="patient-composer__input"
              placeholder={t('inputPlaceholder')}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleTextSubmit() }}
              aria-label={t('inputPlaceholder')}
            />
            {inputText.trim() ? (
              <button className="patient-composer__send" onClick={handleTextSubmit} aria-label={t('sendAria')}>
                <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
                  <path d="M2 21l21-9L2 3v7l15 2-15 2v7z" />
                </svg>
              </button>
            ) : (
              <button
                className="patient-composer__mic"
                onPointerDown={handleMicPointerDown}
                onPointerUp={handleMicPointerUp}
                onPointerMove={handleMicPointerMove}
                onClick={handleMicClick}
                aria-label={t('micAria')}
                disabled={!hasSupport}
                title={hasSupport ? t('micHoldHint') : t('micUnsupported')}
              >
                <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
                  <path d="M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3z" />
                  <path d="M19 11a7 7 0 01-14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              </button>
            )}
          </div>
        </div>
      )}

      {isDone && (
        <div className="patient-done-bar">
          <span>{t('doneBar')}</span>
        </div>
      )}
    </div>
  )
}

// ── Helpers ──
function buildPatientData(existingMessages, text, qIndex) {
  return {
    chart: {
      chiefComplaint: { extracted: qIndex === 0 ? text : '', words: qIndex === 0 ? text : '' },
      location: { extracted: qIndex === 1 ? text : '', words: qIndex === 1 ? text : '' },
      onset: { extracted: qIndex === 2 ? text : '', words: qIndex === 2 ? text : '' },
      quality: { extracted: qIndex === 3 ? text : '', words: qIndex === 3 ? text : '' },
      aggravating: { extracted: qIndex === 4 ? text : '', words: qIndex === 4 ? text : '' },
      associated: { extracted: qIndex === 5 ? text : '', words: qIndex === 5 ? text : '' },
    },
    suggestedTier: 3,
    redFlags: [],
    englishSummary: 'Sample summary — not model output.',
    spanishReadback: 'Resumen de muestra — no es salida del modelo.',
  }
}

function buildScenarioData(lang) {
  const ans = SAMPLE_ANSWERS[lang]
  return {
    chart: {
      chiefComplaint: { extracted: 'Dolor torácico opresivo severo', words: ans[1] },
      location: { extracted: 'Centro de pecho, irradiación a brazo izquierdo', words: ans[2] },
      onset: { extracted: 'Inicio súbito hace ~1 hora, en reposo', words: ans[3] },
      quality: { extracted: 'Opresivo, intensidad 9/10', words: ans[4] },
      aggravating: { extracted: 'No mejora con el reposo', words: ans[5] },
      associated: { extracted: 'Pendiente — pregunta 6 no respondida', words: '' },
    },
    suggestedTier: 2,
    redFlags: ['Dolor torácico opresivo', 'Irradiación a brazo izq.'],
    englishSummary: 'Sample scenario — not model output. Chest pain with radiation, pending red-flag question.',
    spanishReadback: 'Escenario de muestra — no es salida del modelo. Dolor torácico con irradiación, pregunta de banderas rojas pendiente.',
  }
}
