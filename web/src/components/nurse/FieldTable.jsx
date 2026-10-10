import React, { useState, useEffect } from 'react'
import { CHART_FIELDS } from '../../mockData.js'

// ════════════════════════════════════════════════════════════════
// Field correction table: Field / Extracted value / Patient's words / OK or Correct
// Allows editing extracted values and marking fields correct.
// ════════════════════════════════════════════════════════════════

export default function FieldTable({ chart, onAllCorrect }) {
  const [fields, setFields] = useState(() =>
    CHART_FIELDS.map((f) => ({
      ...f,
      extracted: chart[f.key]?.extracted || '',
      words: chart[f.key]?.words || '',
      correct: false,
    }))
  )

  // Reset when chart changes
  useEffect(() => {
    setFields(CHART_FIELDS.map((f) => ({
      ...f,
      extracted: chart[f.key]?.extracted || '',
      words: chart[f.key]?.words || '',
      correct: false,
    })))
  }, [chart])

  const toggleCorrect = (idx) => {
    setFields((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], correct: !next[idx].correct }
      return next
    })
  }

  const editExtracted = (idx, value) => {
    setFields((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], extracted: value }
      return next
    })
  }

  const markAllCorrect = () => {
    setFields((prev) => prev.map((f) => ({ ...f, correct: true })))
    if (onAllCorrect) onAllCorrect()
  }

  const allCorrect = fields.every((f) => f.correct)

  return (
    <div className="field-table-section">
      <div className="field-table-section__header">
        <span className="win-groupbox-label">Revisión de campos extraídos</span>
        <button
          className={`win-btn win-btn--small ${allCorrect ? 'win-btn--success' : ''}`}
          onClick={markAllCorrect}
          title="Marcar todos como correctos"
        >
          ✓ Marcar todos correctos
        </button>
      </div>
      <div className="field-table-wrap">
        <table className="field-table">
          <thead>
            <tr>
              <th style={{ width: '140px' }}>Campo</th>
              <th>Valor extraído</th>
              <th style={{ width: '30%' }}>Palabras del paciente</th>
              <th style={{ width: '70px' }}>OK</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f, idx) => (
              <tr key={f.key} className={f.correct ? 'field-row--correct' : ''}>
                <td className="field-label">{f.label}</td>
                <td>
                  <input
                    type="text"
                    className="field-input"
                    value={f.extracted}
                    onChange={(e) => editExtracted(idx, e.target.value)}
                    aria-label={`Valor extraído: ${f.label}`}
                  />
                </td>
                <td className="field-words">"{f.words}"</td>
                <td className="field-ok">
                  <button
                    className={`field-ok-btn ${f.correct ? 'field-ok-btn--checked' : ''}`}
                    onClick={() => toggleCorrect(idx)}
                    aria-label={`Marcar ${f.label} como correcto`}
                    aria-pressed={f.correct}
                  >
                    {f.correct ? '✓' : ''}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
