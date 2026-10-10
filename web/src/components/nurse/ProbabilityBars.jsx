import React from 'react'
import { TIER_COLORS } from '../../mockData.js'
import { makeT } from '../../i18n.js'

// ════════════════════════════════════════════════════════════════
// Probability bars + expected loss values
// SAMPLE VALUES — NOT MODEL OUTPUT
// ════════════════════════════════════════════════════════════════

export default function ProbabilityBars({ probabilities, suggestedTier, lang = 'en' }) {
  const t = makeT(lang, 'nurse')

  return (
    <div className="prob-section">
      <div className="prob-section__header">
        <span className="win-groupbox-label">{t('probHeader')}</span>
        <span className="prob-section__sample-tag">SAMPLE VALUES — NOT MODEL OUTPUT</span>
      </div>
      <div className="prob-section__body">
        {probabilities.length === 0 && (
          <p className="prob-section__pending">
            {lang === 'es' ? 'Pendiente — IA no conectada' : 'Pending — AI not connected'}
          </p>
        )}
        {probabilities.length > 0 && (
          <table className="prob-table">
            <thead>
              <tr>
                <th>ESI</th>
                <th>{t('probCol')}</th>
                <th>{t('lossCol')}</th>
              </tr>
            </thead>
            <tbody>
              {probabilities.map((p) => {
                const colors = TIER_COLORS[p.esi]
                const isSuggested = p.esi === suggestedTier
                return (
                  <tr key={p.esi} className={isSuggested ? 'prob-row--suggested' : ''}>
                    <td>
                      <span className="prob-tier-badge" style={{ background: colors.bg, color: colors.text }}>
                        {p.esi}
                      </span>
                      {isSuggested && <span className="prob-suggested-arrow">◄ {t('suggested')}</span>}
                    </td>
                    <td>
                      <div className="prob-bar-wrap">
                        <div className="prob-bar-fill" style={{ width: `${p.probability * 100}%`, background: colors.bg }} />
                        <span className="prob-bar-label">{(p.probability * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="prob-loss">{p.expectedLoss.toFixed(2)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
