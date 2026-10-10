import React from 'react'

export default function RecordingBar({ seconds, isLocked, onStop, onCancel, onLock, lang = 'es' }) {
  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const lockHint = lang === 'es' ? '↑ Deslizar para bloquear' : '↑ Slide up to lock'
  const stopLabel = lang === 'es' ? 'Detener' : 'Stop'
  const cancelAria = lang === 'es' ? 'Cancelar grabación' : 'Cancel recording'
  const stopAria = lang === 'es' ? 'Detener y enviar' : 'Stop and send'

  return (
    <div className="recording-bar" role="status" aria-live="polite">
      <div className="recording-bar__indicator">
        <span className="recording-bar__dot" />
        <span className="recording-bar__timer">{formatTime(seconds)}</span>
      </div>
      <div className="recording-bar__wave">
        {Array.from({ length: 20 }, (_, i) => (
          <div
            key={i}
            className="recording-bar__wave-bar"
            style={{
              animationDelay: `${i * 0.05}s`,
              height: `${20 + ((i * 37) % 60)}%`,
            }}
          />
        ))}
      </div>
      {!isLocked ? (
        <>
          <div className="recording-bar__hint">
            <span className="recording-bar__lock-hint">{lockHint}</span>
          </div>
          <button
            className="recording-bar__cancel"
            onClick={onCancel}
            aria-label={cancelAria}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </>
      ) : (
        <button
          className="recording-bar__stop"
          onClick={onStop}
          aria-label={stopAria}
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
          <span>{stopLabel}</span>
        </button>
      )}
    </div>
  )
}
