import React from 'react'

export default function ProgressDots({ current, total, answered, lang = 'es' }) {
  const answeredLabel = lang === 'es' ? 'respondida' : 'answered'
  const pendingLabel = lang === 'es' ? 'pendiente' : 'pending'
  const questionLabel = lang === 'es' ? 'Pregunta' : 'Question'

  return (
    <div className="progress-dots" role="progressbar" aria-valuenow={current} aria-valuemax={total} aria-valuemin={0}>
      {Array.from({ length: total }, (_, i) => {
        const isAnswered = answered[i]
        const isCurrent = i === current
        return (
          <div
            key={i}
            className={`progress-dot ${isAnswered ? 'progress-dot--done' : ''} ${isCurrent ? 'progress-dot--current' : ''}`}
            aria-label={`${questionLabel} ${i + 1} ${isAnswered ? answeredLabel : pendingLabel}`}
          >
            {isAnswered ? (
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <span>{i + 1}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
