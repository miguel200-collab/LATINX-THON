import React, { useState, useEffect, useRef, useCallback } from 'react'
import { sessionStore } from '../mockSessionStore.js'
import { TIER_COLORS, tierLabel, tierLabelShort } from '../mockData.js'
import {
  confirmESI,
  fetchQueue,
  fetchSessionDetail,
  mapBackendSessionToCase,
  checkBackendHealth,
} from '../triageApi.js'
import { makeT } from '../i18n.js'
import LanguageToggle from '../components/LanguageToggle.jsx'
import ProbabilityBars from '../components/nurse/ProbabilityBars.jsx'
import FieldTable from '../components/nurse/FieldTable.jsx'
import { IntakeSheetPreview, ConfirmedSheetPreview } from '../components/nurse/SheetPreview.jsx'
import VoiceNotePlayer from '../components/patient/VoiceNotePlayer.jsx'
import '../styles/nurse.css'

export default function NursePage({ lang: langProp, setLang: setLangProp }) {
  // Nurse defaults to English; StaffSignIn passes lang/setLang through.
  const [internalLang, setInternalLang] = useState('en')
  const lang = langProp ?? internalLang
  const setLang = setLangProp ?? setInternalLang
  const t = makeT(lang, 'nurse')

  const [localQueue, setLocalQueue] = useState([])
  const [backendCases, setBackendCases] = useState([])
  const [backendLive, setBackendLive] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [selectedESI, setSelectedESI] = useState(null)
  const [isConfirming, setIsConfirming] = useState(false)
  const [reviewSeconds, setReviewSeconds] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [showSaveError, setShowSaveError] = useState(false)
  const [showSheets, setShowSheets] = useState(false)
  const timerRef = useRef(null)

  // Subscribe to local session store
  useEffect(() => {
    const unsub = sessionStore.subscribe((q) => setLocalQueue([...q]))
    return unsub
  }, [])

  // Poll backend queue and merge live cases
  useEffect(() => {
    let active = true
    async function loadBackendQueue() {
      try {
        const health = await checkBackendHealth()
        if (!active) return
        if (health.ok) {
          setBackendLive(true)
          const res = await fetchQueue()
          if (!active) return
          if (res && Array.isArray(res.patients)) {
            const details = await Promise.all(
              res.patients.map(async (p) => {
                try {
                  const detail = await fetchSessionDetail(p.id)
                  return mapBackendSessionToCase(detail)
                } catch (e) {
                  return null
                }
              })
            )
            const valid = details.filter(Boolean)
            if (active) setBackendCases(valid)
          }
        } else {
          setBackendLive(false)
        }
      } catch (e) {
        if (active) setBackendLive(false)
      }
    }
    loadBackendQueue()
    const interval = setInterval(loadBackendQueue, 3500)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  // Merged queue: live backend cases at top, preset samples below
  const queue = [
    ...backendCases,
    ...localQueue.filter((l) => !backendCases.some((b) => b.id === l.id)),
  ]

  // Auto-select first case
  useEffect(() => {
    if (!selectedId && queue.length > 0) {
      setSelectedId(queue[0].id)
    }
    if (selectedId && !queue.find((c) => c.id === selectedId)) {
      setSelectedId(queue[0]?.id || null)
    }
  }, [queue, selectedId])

  // Review timer
  useEffect(() => {
    if (selectedId) {
      setReviewSeconds(0)
      setSelectedESI(null)
      setShowSaveError(false)
      setShowSheets(false)
      const selected = queue.find((c) => c.id === selectedId)
      if (selected?.confirmedESI) {
        setReviewSeconds(selected.reviewSeconds || 0)
      } else {
        timerRef.current = setInterval(() => {
          setReviewSeconds((s) => s + 1)
        }, 1000)
      }
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [selectedId])

  const selectedCase = queue.find((c) => c.id === selectedId)

  const handleSelectCase = useCallback((id) => {
    setSelectedId(id)
  }, [])

  const handleResetQueue = useCallback(() => {
    sessionStore.resetQueue()
    setSelectedESI(null)
    setShowSheets(false)
  }, [])

  const handleConfirm = useCallback(async () => {
    if (!selectedESI || !selectedCase || isConfirming) return
    setIsConfirming(true)
    if (timerRef.current) clearInterval(timerRef.current)
    const elapsed = reviewSeconds
    try {
      await confirmESI(selectedCase.id, selectedESI, elapsed)
      sessionStore.updateCase(selectedCase.id, {
        confirmedESI: selectedESI,
        confirmedAt: new Date().toISOString(),
        reviewSeconds: elapsed,
        status: 'confirmed',
      })
      if (selectedCase.id.startsWith('s-')) {
        setBackendCases((prev) =>
          prev.map((c) =>
            c.id === selectedCase.id
              ? { ...c, confirmedESI: selectedESI, confirmedAt: new Date().toISOString(), reviewSeconds: elapsed, status: 'confirmed' }
              : c
          )
        )
      }
    } catch (e) {
      setShowSaveError(true)
    }
    setIsConfirming(false)
  }, [selectedESI, selectedCase, isConfirming, reviewSeconds])


  const handleSimulateLoading = useCallback(() => {
    setIsLoading(true)
    setTimeout(() => setIsLoading(false), 2000)
  }, [])

  const handleSimulateError = useCallback(() => {
    setShowSaveError(true)
  }, [])

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  const audioNotes = selectedCase
    ? (selectedCase.audioNotes && selectedCase.audioNotes.length > 0
        ? selectedCase.audioNotes
        : sessionStore.getAudioNotes(selectedCase.id))
    : []

  return (
    <div className="nurse-page">
      {/* ── Title bar (navy gradient) ── */}
      <div className="nurse-titlebar">
        <div className="nurse-titlebar__icon">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="#fff">
            <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-7 14h-2v-4H6v-2h4V7h2v4h4v2h-4v4z" />
          </svg>
        </div>
        <div className="nurse-titlebar__title">{t('titlebar')}</div>
        <div className="nurse-titlebar__demo">DEMO — SAMPLE DATA</div>
        <div className="nurse-titlebar__controls">
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--min" title={t('minLabel')} />
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--max" title={t('maxLabel')} />
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--close" title={t('closeLabel')} />
        </div>
      </div>

      {/* ── Toolbar ── */}
      <div className="nurse-toolbar">
        <button className="win-btn" onClick={handleResetQueue} title={t('resetQueue')}>
          {t('resetQueue')}
        </button>
        <div className="nurse-toolbar__sep" />
        <button className="win-btn win-btn--preview" onClick={handleSimulateLoading} title={t('viewLoading')}>
          {t('viewLoading')}
        </button>
        <button className="win-btn win-btn--preview" onClick={handleSimulateError} title={t('viewError')}>
          {t('viewError')}
        </button>
        <div className="nurse-toolbar__spacer" />
        <LanguageToggle lang={lang} setLang={setLang} variant="dark" />
        <div className="nurse-toolbar__sep" />
        <span className="nurse-toolbar__disclaimer">{t('disclaimer')}</span>
      </div>

      {/* ── Main content ── */}
      <div className="nurse-main">
        {/* Left pane: patient queue */}
        <div className="nurse-queue">
          <div className="nurse-queue__header">
            <span>{t('queueHeader')} ({queue.length})</span>
          </div>
          <div className="nurse-queue__list">
            {isLoading && (
              <div className="nurse-loading">
                <div className="nurse-loading__spinner" />
                <span>{t('loadingCases')}</span>
              </div>
            )}
            {!isLoading && queue.length === 0 && (
              <div className="nurse-empty">
                <div className="nurse-empty__icon">📋</div>
                <div className="nurse-empty__title">{t('queueEmpty')}</div>
                <div className="nurse-empty__msg">{t('queueEmptyMsg')}</div>
                <button className="win-btn" onClick={handleResetQueue}>{t('resetQueueBtn')}</button>
              </div>
            )}
            {!isLoading && queue.map((c) => {
              const colors = TIER_COLORS[c.suggestedTier]
              const isSelected = c.id === selectedId
              return (
                <div
                  key={c.id}
                  className={`queue-item ${isSelected ? 'queue-item--selected' : ''} ${c.status === 'confirmed' ? 'queue-item--confirmed' : ''}`}
                  onClick={() => handleSelectCase(c.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSelectCase(c.id) }}
                >
                  <div className="queue-item__tier" style={{ background: colors.bg, color: colors.text }}>
                    {c.suggestedTier}
                  </div>
                  <div className="queue-item__body">
                    <div className="queue-item__id">{c.id}</div>
                    <div className="queue-item__meta">
                      <span className="queue-item__label">{c.label}</span>
                      <span className="queue-item__wait">⏱ {c.waitingMinutes} min</span>
                      {c.status === 'confirmed' && <span className="queue-item__confirmed">{t('confirmedTag')}</span>}
                    </div>
                    {c.redFlags.length > 0 && (
                      <div className="queue-item__flags">
                        {c.redFlags.slice(0, 2).map((f, i) => (
                          <span key={i} className="queue-item__flag">🚩 {f}</span>
                        ))}
                        {c.redFlags.length > 2 && <span className="queue-item__flag">+{c.redFlags.length - 2}</span>}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right pane: patient chart */}
        <div className="nurse-chart">
          {!selectedCase ? (
            <div className="nurse-chart__empty">
              <div className="nurse-empty__icon">🏥</div>
              <div className="nurse-empty__title">{t('selectPatient')}</div>
              <div className="nurse-empty__msg">{t('selectPatientMsg')}</div>
            </div>
          ) : (
            <div className="nurse-chart__content">
              {/* Patient info bar */}
              <div className="chart-info-bar">
                <div className="chart-info-bar__left">
                  <span className="chart-info-bar__id">{selectedCase.id}</span>
                  <span className="chart-info-bar__label">{selectedCase.label}</span>
                  <span className="chart-info-bar__patient">{selectedCase.patient.age} {t('yearsOld')}, {selectedCase.patient.sex}</span>
                  <span className="chart-info-bar__wait">{t('waitTime')} {selectedCase.waitingMinutes} min</span>
                </div>
                <div className="chart-info-bar__right">
                  <span className="chart-info-bar__timer-label">{t('reviewTime')}</span>
                  <span className="chart-info-bar__timer">{formatTime(reviewSeconds)}</span>
                </div>
              </div>

              {/* Suggested tier */}
              <div className="chart-tier-section">
                <div className="chart-tier-section__label">{t('suggestedTier')}</div>
                <div className="chart-tier-section__badge" style={{ background: TIER_COLORS[selectedCase.suggestedTier].bg, color: TIER_COLORS[selectedCase.suggestedTier].text }}>
                  {tierLabel(selectedCase.suggestedTier, lang)}
                </div>
                <span className="chart-tier-section__note">{t('suggestedNote')}</span>
              </div>

              {/* Probability bars */}
              <ProbabilityBars probabilities={selectedCase.probabilities} suggestedTier={selectedCase.suggestedTier} lang={lang} />

              {/* Summaries */}
              <div className="chart-summary-section">
                <div className="chart-summary-section__header">
                  <span className="win-groupbox-label">{t('summariesHeader')}</span>
                  <span className="chart-summary-section__tag">SAMPLE VALUES — NOT MODEL OUTPUT</span>
                </div>
                <div className="chart-summary-section__body">
                  <div className="chart-summary">
                    <div className="chart-summary__label">{t('englishSummaryLabel')}</div>
                    <div className="chart-summary__text">{selectedCase.englishSummary}</div>
                  </div>
                  <div className="chart-summary">
                    <div className="chart-summary__label">{t('spanishReadbackLabel')}</div>
                    <div className="chart-summary__text">{selectedCase.spanishReadback}</div>
                  </div>
                </div>
              </div>

              {/* Field table */}
              <FieldTable chart={selectedCase.chart} lang={lang} />

              {/* Audio notes */}
              {audioNotes.length > 0 && (
                <div className="chart-audio-section">
                  <div className="chart-audio-section__header">
                    <span className="win-groupbox-label">{t('audioNotes')}</span>
                  </div>
                  <div className="chart-audio-section__body">
                    {audioNotes.map((note, i) => (
                      <VoiceNotePlayer key={note.id} url={note.url} duration={note.duration} timestamp={`${lang === 'es' ? 'Nota' : 'Note'} ${i + 1}`} lang={lang} />
                    ))}
                  </div>
                </div>
              )}

              {/* ESI selection + confirmation */}
              <div className="chart-esi-section">
                <div className="chart-esi-section__header">
                  <span className="win-groupbox-label">{t('esiAssignment')}</span>
                </div>
                <div className="chart-esi-section__body">
                  {selectedCase.confirmedESI ? (
                    <div className="chart-confirmed">
                      <div className="chart-confirmed__icon">✓</div>
                      <div className="chart-confirmed__text">
                        <strong>{t('demoConfirmation')}</strong>
                        <div>{t('esiAssigned')} <span className="chart-confirmed__esi" style={{ background: TIER_COLORS[selectedCase.confirmedESI].bg, color: TIER_COLORS[selectedCase.confirmedESI].text }}>{selectedCase.confirmedESI}</span></div>
                        <div>{t('reviewTime')} {formatTime(selectedCase.reviewSeconds || reviewSeconds)}</div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="chart-esi-buttons">
                        {[1, 2, 3, 4, 5].map((esi) => (
                          <button
                            key={esi}
                            className={`esi-btn ${selectedESI === esi ? 'esi-btn--selected' : ''}`}
                            style={{
                              borderColor: selectedESI === esi ? TIER_COLORS[esi].bg : '#aaa',
                              background: selectedESI === esi ? TIER_COLORS[esi].light : '#fff',
                            }}
                            onClick={() => setSelectedESI(esi)}
                            aria-label={`${t('confirmEsi')} ${esi}`}
                            aria-pressed={selectedESI === esi}
                          >
                            <span className="esi-btn__num" style={{ background: TIER_COLORS[esi].bg, color: TIER_COLORS[esi].text }}>{esi}</span>
                            <span className="esi-btn__label">{tierLabelShort(esi, lang)}</span>
                          </button>
                        ))}
                      </div>
                      <button
                        className="win-btn win-btn--confirm"
                        disabled={!selectedESI || isConfirming}
                        onClick={handleConfirm}
                      >
                        {isConfirming ? t('confirming') : selectedESI ? `${t('confirmEsi')} ${selectedESI}` : t('selectEsiPrompt')}
                      </button>
                      {!selectedESI && <span className="chart-esi-hint">{t('mustSelectEsi')}</span>}
                    </>
                  )}
                </div>
              </div>

              {/* Save error */}
              {showSaveError && (
                <div className="chart-save-error">
                  <div className="chart-save-error__icon">⚠</div>
                  <div>
                    <strong>{t('saveErrorTitle')}</strong>
                    <div>{t('saveErrorMsg')}</div>
                  </div>
                  <button className="chart-save-error__close" onClick={() => setShowSaveError(false)}>×</button>
                </div>
              )}

              {/* Sheet previews & official PDF */}
              <div className="chart-sheets-section">
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <button className="win-btn win-btn--toggle" onClick={() => setShowSheets(!showSheets)}>
                    {showSheets ? '▼' : '▶'} {t('sheetsToggle')}
                  </button>
                  {selectedCase.pdfUrl && (
                    <a
                      className="win-btn"
                      href={selectedCase.pdfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    >
                      🖨 {lang === 'es' ? 'Descargar PDF Oficial' : 'Download Official PDF'}
                    </a>
                  )}
                </div>
                {showSheets && (
                  <div className="chart-sheets-grid">
                    <IntakeSheetPreview caseData={selectedCase} lang={lang} />
                    {selectedCase.confirmedESI && <ConfirmedSheetPreview caseData={selectedCase} lang={lang} />}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Status bar ── */}
      <div className="nurse-statusbar">
        <span className="nurse-statusbar__item">
          {queue.length} {t('statusQueue')}
        </span>
        <span className="nurse-statusbar__sep" />
        <span className="nurse-statusbar__item">
          {queue.filter((c) => c.status === 'confirmed').length} {t('statusConfirmed')}
        </span>
        <span className="nurse-statusbar__sep" />
        <span className={`nurse-statusbar__item ${backendLive ? 'nurse-statusbar__item--live' : 'nurse-statusbar__item--warn'}`} style={{ color: backendLive ? '#006400' : '#856404' }}>
          {backendLive ? '● ENGINE: LIVE (WHISPER + GEMINI + JEV)' : '⚠ DEMO — SAMPLE DATA'}
        </span>
        <span className="nurse-statusbar__spacer" />
        <span className="nurse-statusbar__item nurse-statusbar__item--disclaimer">
          {t('disclaimer')}
        </span>
      </div>
    </div>
  )
}
