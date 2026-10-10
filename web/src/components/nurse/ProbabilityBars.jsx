import React from 'react'
import { TIER_COLORS } from '../../mockData.js'

// ════════════════════════════════════════════════════════════════
// Probability bars + expected loss values
// SAMPLE VALUES — NOT MODEL OUTPUT
// ════════════════════════════════════════════════════════════════

export default function ProbabilityBars({ probabilities, suggestedTier }) {
  return (
    <div className="prob-section">
      <div className="prob-section__header">
        <span className="win-groupbox-label">Probabilidades ESI y pérdida esperada</span>
        <span className="prob-section__sample-tag">SAMPLE VALUES — NOT MODEL OUTPUT</span>
      </div>
      <div className="prob-section__body">
        <table className="prob-table">
          <thead>
            <tr>
              <th>ESI</th>
              <th>Probabilidad</th>
              <th>Pérdida esperada</th>
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
                    {isSuggested && <span className="prob-suggested-arrow">◄ sugerido</span>}
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
      </div>
    </div>
  )
}
