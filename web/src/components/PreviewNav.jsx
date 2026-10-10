import React from 'react'

export default function PreviewNav({ view, setView }) {
  return (
    <div className="preview-nav" role="navigation" aria-label="Demo view switcher">
      <div className="preview-nav__demo-badge" aria-label="Demo mode">
        <span>⚠</span>
        DEMO — SAMPLE DATA
      </div>
      <div className="preview-nav__switcher">
        <button
          className={`preview-nav__btn ${view === 'patient' ? 'preview-nav__btn--active' : ''}`}
          onClick={() => setView('patient')}
          aria-pressed={view === 'patient'}
        >
          📱 Paciente
        </button>
        <button
          className={`preview-nav__btn ${view === 'nurse' ? 'preview-nav__btn--active' : ''}`}
          onClick={() => setView('nurse')}
          aria-pressed={view === 'nurse'}
        >
          🖥️ Enfermería
        </button>
      </div>
    </div>
  )
}
