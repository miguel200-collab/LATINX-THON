import React, { useState, useEffect } from 'react'
import { CHART_FIELDS, fieldLabel } from '../../mockData.js'
import { makeT } from '../../i18n.js'

// ════════════════════════════════════════════════════════════════
// Field correction table: Field / Extracted value / Patient's words / OK or Correct
// Allows editing extracted values and marking fields correct.
// Patient's words are NEVER translated — they stay in the original language.
// ════════════════════════════════════════════════════════════════

export default function FieldTable({ chart, onAllCorrect, lang = 'en' }) {
  const t = makeT(lang, 'nurse')

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
        <span className="win-groupbox-label">{t('fieldReview')}</span>
        <button
          className={`win-btn win-btn--small ${allCorrect ? 'win-btn--success' : ''}`}
          onClick={markAllCorrect}
          title={t('markAllCorrect')}
        >
          {t('markAllCorrect')}
        </button>
      </div>
      <div className="field-table-wrap">
        <table className="field-table">
          <thead>
            <tr>
              <th style={{ width: '140px' }}>{t('fieldCol')}</th>
              <th>{t('extractedCol')}</th>
              <th style={{ width: '30%' }}>{t('wordsCol')}</th>
              <th style={{ width: '70px' }}>{t('okCol')}</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f, idx) => (
              <tr key={f.key} className={f.correct ? 'field-row--correct' : ''}>
                <td className="field-label">{fieldLabel(f, lang)}</td>
                <td>
                  <input
                    type="text"
                    className="field-input"
                    value={f.extracted}
                    onChange={(e) => editExtracted(idx, e.target.value)}
                    aria-label={`${t('extractedCol')}: ${fieldLabel(f, lang)}`}
                  />
                </td>
                <td className="field-words">"{f.words}"</td>
                <td className="field-ok">
                  <button
                    className={`field-ok-btn ${f.correct ? 'field-ok-btn--checked' : ''}`}
                    onClick={() => toggleCorrect(idx)}
                    aria-label={`${fieldLabel(f, lang)} OK`}
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
