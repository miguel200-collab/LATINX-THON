import React, { useState, useEffect, useRef, useCallback } from 'react'
import { sessionStore } from '../mockSessionStore.js'
import { TIER_COLORS, simulateConfirmESI } from '../mockData.js'
import ProbabilityBars from '../components/nurse/ProbabilityBars.jsx'
import FieldTable from '../components/nurse/FieldTable.jsx'
import { IntakeSheetPreview, ConfirmedSheetPreview } from '../components/nurse/SheetPreview.jsx'
import VoiceNotePlayer from '../components/patient/VoiceNotePlayer.jsx'
import '../styles/nurse.css'

export default function NursePage() {
  const [queue, setQueue] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selectedESI, setSelectedESI] = useState(null)
  const [isConfirming, setIsConfirming] = useState(false)
  const [reviewSeconds, setReviewSeconds] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [showSaveError, setShowSaveError] = useState(false)
  const [showSheets, setShowSheets] = useState(false)
  const timerRef = useRef(null)

  // Subscribe to session store
  useEffect(() => {
    const unsub = sessionStore.subscribe((q) => setQueue([...q]))
    return unsub
  }, [])

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
      await simulateConfirmESI(selectedCase.id, selectedESI)
      sessionStore.updateCase(selectedCase.id, {
        confirmedESI: selectedESI,
        confirmedAt: new Date().toISOString(),
        reviewSeconds: elapsed,
        status: 'confirmed',
      })
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

  const audioNotes = selectedCase ? sessionStore.getAudioNotes(selectedCase.id) : []

  return (
    <div className="nurse-page">
      {/* ── Title bar (navy gradient) ── */}
      <div className="nurse-titlebar">
        <div className="nurse-titlebar__icon">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="#fff">
            <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-7 14h-2v-4H6v-2h4V7h2v4h4v2h-4v4z" />
          </svg>
        </div>
        <div className="nurse-titlebar__title">Estación de enfermería — cola de triage</div>
        <div className="nurse-titlebar__demo">DEMO — SAMPLE DATA</div>
        <div className="nurse-titlebar__controls">
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--min" title="Minimizar (decorativo)" />
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--max" title="Maximizar (decorativo)" />
          <span className="nurse-titlebar__ctrl nurse-titlebar__ctrl--close" title="Cerrar (decorativo)" />
        </div>
      </div>

      {/* ── Toolbar ── */}
      <div className="nurse-toolbar">
        <button className="win-btn" onClick={handleResetQueue} title="Restablecer cola de muestra">
          ↻ Restablecer cola
        </button>
        <div className="nurse-toolbar__sep" />
        <button className="win-btn win-btn--preview" onClick={handleSimulateLoading} title="Ver estado de carga">
          ⟳ Ver: cargando
        </button>
        <button className="win-btn win-btn--preview" onClick={handleSimulateError} title="Ver estado de error">
          ⚠ Ver: error de guardado
        </button>
        <div className="nurse-toolbar__spacer" />
        <span className="nurse-toolbar__disclaimer">Administrative intake aid. Not a diagnosis. The RN assigns ESI.</span>
      </div>

      {/* ── Main content ── */}
      <div className="nurse-main">
        {/* Left pane: patient queue */}
        <div className="nurse-queue">
          <div className="nurse-queue__header">
            <span>Cola de pacientes ({queue.length})</span>
          </div>
          <div className="nurse-queue__list">
            {isLoading && (
              <div className="nurse-loading">
                <div className="nurse-loading__spinner" />
                <span>Cargando casos...</span>
              </div>
            )}
            {!isLoading && queue.length === 0 && (
              <div className="nurse-empty">
                <div className="nurse-empty__icon">📋</div>
                <div className="nurse-empty__title">Cola vacía</div>
                <div className="nurse-empty__msg">No hay pacientes en espera.</div>
                <button className="win-btn" onClick={handleResetQueue}>Restablecer cola de muestra</button>
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
                      {c.status === 'confirmed' && <span className="queue-item__confirmed">✓ Confirmado</span>}
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
              <div className="nurse-empty__title">Seleccione un paciente</div>
              <div className="nurse-empty__msg">Elija un caso de la cola para ver el detalle.</div>
            </div>
          ) : (
            <div className="nurse-chart__content">
              {/* Patient info bar */}
              <div className="chart-info-bar">
                <div className="chart-info-bar__left">
                  <span className="chart-info-bar__id">{selectedCase.id}</span>
                  <span className="chart-info-bar__label">{selectedCase.label}</span>
                  <span className="chart-info-bar__patient">{selectedCase.patient.age} años, {selectedCase.patient.sex}</span>
                  <span className="chart-info-bar__wait">Espera: {selectedCase.waitingMinutes} min</span>
                </div>
                <div className="chart-info-bar__right">
                  <span className="chart-info-bar__timer-label">Tiempo de revisión:</span>
                  <span className="chart-info-bar__timer">{formatTime(reviewSeconds)}</span>
                </div>
              </div>

              {/* Suggested tier */}
              <div className="chart-tier-section">
                <div className="chart-tier-section__label">Tier de revisión sugerido:</div>
                <div className="chart-tier-section__badge" style={{ background: TIER_COLORS[selectedCase.suggestedTier].bg, color: TIER_COLORS[selectedCase.suggestedTier].text }}>
                  Nivel {selectedCase.suggestedTier} — {TIER_COLORS[selectedCase.suggestedTier].label.split(' — ')[1]}
                </div>
                <span className="chart-tier-section__note">Sugerido por el sistema — la enfermera asigna el ESI oficial</span>
              </div>

              {/* Probability bars */}
              <ProbabilityBars probabilities={selectedCase.probabilities} suggestedTier={selectedCase.suggestedTier} />

              {/* Summaries */}
              <div className="chart-summary-section">
                <div className="chart-summary-section__header">
                  <span className="win-groupbox-label">Resúmenes</span>
                  <span className="chart-summary-section__tag">SAMPLE VALUES — NOT MODEL OUTPUT</span>
                </div>
                <div className="chart-summary-section__body">
                  <div className="chart-summary">
                    <div className="chart-summary__label">English summary:</div>
                    <div className="chart-summary__text">{selectedCase.englishSummary}</div>
                  </div>
                  <div className="chart-summary">
                    <div className="chart-summary__label">Lectura en español (read-back):</div>
                    <div className="chart-summary__text">{selectedCase.spanishReadback}</div>
                  </div>
                </div>
              </div>

              {/* Field table */}
              <FieldTable chart={selectedCase.chart} />

              {/* Audio notes */}
              {audioNotes.length > 0 && (
                <div className="chart-audio-section">
                  <div className="chart-audio-section__header">
                    <span className="win-groupbox-label">Notas de voz del paciente</span>
                  </div>
                  <div className="chart-audio-section__body">
                    {audioNotes.map((note, i) => (
                      <VoiceNotePlayer key={note.id} url={note.url} duration={note.duration} timestamp={`Nota ${i + 1}`} />
                    ))}
                  </div>
                </div>
              )}

              {/* ESI selection + confirmation */}
              <div className="chart-esi-section">
                <div className="chart-esi-section__header">
                  <span className="win-groupbox-label">Asignación de ESI oficial</span>
                </div>
                <div className="chart-esi-section__body">
                  {selectedCase.confirmedESI ? (
                    <div className="chart-confirmed">
                      <div className="chart-confirmed__icon">✓</div>
                      <div className="chart-confirmed__text">
                        <strong>Demo confirmation</strong>
                        <div>ESI asignado: <span className="chart-confirmed__esi" style={{ background: TIER_COLORS[selectedCase.confirmedESI].bg, color: TIER_COLORS[selectedCase.confirmedESI].text }}>{selectedCase.confirmedESI}</span></div>
                        <div>Tiempo de revisión: {formatTime(selectedCase.reviewSeconds || reviewSeconds)}</div>
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
                            aria-label={`Asignar ESI ${esi}`}
                            aria-pressed={selectedESI === esi}
                          >
                            <span className="esi-btn__num" style={{ background: TIER_COLORS[esi].bg, color: TIER_COLORS[esi].text }}>{esi}</span>
                            <span className="esi-btn__label">{TIER_COLORS[esi].label.split(' — ')[1]}</span>
                          </button>
                        ))}
                      </div>
                      <button
                        className="win-btn win-btn--confirm"
                        disabled={!selectedESI || isConfirming}
                        onClick={handleConfirm}
                      >
                        {isConfirming ? 'Confirmando...' : selectedESI ? `Confirmar ESI ${selectedESI}` : 'Seleccione un ESI para confirmar'}
                      </button>
                      {!selectedESI && <span className="chart-esi-hint">⚠ Debe seleccionar un ESI antes de confirmar</span>}
                    </>
                  )}
                </div>
              </div>

              {/* Save error */}
              {showSaveError && (
                <div className="chart-save-error">
                  <div className="chart-save-error__icon">⚠</div>
                  <div>
                    <strong>Error de guardado (escenario de demostración)</strong>
                    <div>No se pudo guardar la confirmación. Este es un escenario de demostración.</div>
                  </div>
                  <button className="chart-save-error__close" onClick={() => setShowSaveError(false)}>×</button>
                </div>
              )}

              {/* Sheet previews */}
              <div className="chart-sheets-section">
                <button className="win-btn win-btn--toggle" onClick={() => setShowSheets(!showSheets)}>
                  {showSheets ? '▼' : '▶'} Vista previa de hojas
                </button>
                {showSheets && (
                  <div className="chart-sheets-grid">
                    <IntakeSheetPreview caseData={selectedCase} />
                    {selectedCase.confirmedESI && <ConfirmedSheetPreview caseData={selectedCase} />}
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
          {queue.length} paciente(s) en cola
        </span>
        <span className="nurse-statusbar__sep" />
        <span className="nurse-statusbar__item">
          {queue.filter((c) => c.status === 'confirmed').length} confirmado(s)
        </span>
        <span className="nurse-statusbar__sep" />
        <span className="nurse-statusbar__item nurse-statusbar__item--warn">
          ⚠ DEMO — SAMPLE DATA
        </span>
        <span className="nurse-statusbar__spacer" />
        <span className="nurse-statusbar__item nurse-statusbar__item--disclaimer">
          Administrative intake aid. Not a diagnosis. The RN assigns ESI.
        </span>
      </div>
    </div>
  )
}
