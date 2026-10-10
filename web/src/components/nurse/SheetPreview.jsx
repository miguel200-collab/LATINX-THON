import React from 'react'
import { TIER_COLORS } from '../../mockData.js'

// ════════════════════════════════════════════════════════════════
// Sheet preview — intake sheet and confirmed sheet
// Uses frontend sample content, labeled as samples.
// ════════════════════════════════════════════════════════════════

export function IntakeSheetPreview({ caseData }) {
  const colors = TIER_COLORS[caseData.suggestedTier]
  return (
    <div className="sheet-preview">
      <div className="sheet-preview__header">
        <span className="sheet-preview__title">Hoja de admisión (vista previa)</span>
        <span className="sheet-preview__sample-tag">MUESTRA</span>
      </div>
      <div className="sheet-preview__body">
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">ID:</span>
          <span className="sheet-preview__value">{caseData.id} ({caseData.label})</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">Paciente:</span>
          <span className="sheet-preview__value">{caseData.patient.age} años, {caseData.patient.sex}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">Tier sugerido:</span>
          <span className="sheet-preview__tier" style={{ background: colors.bg, color: colors.text }}>
            {caseData.suggestedTier}
          </span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Motivo:</span>
          <span className="sheet-preview__value">{caseData.chart.chiefComplaint?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Localización:</span>
          <span className="sheet-preview__value">{caseData.chart.location?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Inicio:</span>
          <span className="sheet-preview__value">{caseData.chart.onset?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Calidad/Intensidad:</span>
          <span className="sheet-preview__value">{caseData.chart.quality?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Agravantes:</span>
          <span className="sheet-preview__value">{caseData.chart.aggravating?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Asociados:</span>
          <span className="sheet-preview__value">{caseData.chart.associated?.extracted || '—'}</span>
        </div>
        {caseData.redFlags.length > 0 && (
          <>
            <div className="sheet-preview__divider" />
            <div className="sheet-preview__row sheet-preview__row--col">
              <span className="sheet-preview__label sheet-preview__label--red">Banderas rojas:</span>
              <span className="sheet-preview__value">{caseData.redFlags.join(', ')}</span>
            </div>
          </>
        )}
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">ESI oficial:</span>
          <span className="sheet-preview__value sheet-preview__blank">____ (para asignar por la enfermera)</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Firma:</span>
          <span className="sheet-preview__value sheet-preview__blank">________________</span>
        </div>
      </div>
    </div>
  )
}

export function ConfirmedSheetPreview({ caseData }) {
  const colors = TIER_COLORS[caseData.confirmedESI]
  return (
    <div className="sheet-preview sheet-preview--confirmed">
      <div className="sheet-preview__header">
        <span className="sheet-preview__title">Hoja confirmada (vista previa)</span>
        <span className="sheet-preview__sample-tag">MUESTRA</span>
      </div>
      <div className="sheet-preview__body">
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">ID:</span>
          <span className="sheet-preview__value">{caseData.id} ({caseData.label})</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">Paciente:</span>
          <span className="sheet-preview__value">{caseData.patient.age} años, {caseData.patient.sex}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">Tier sugerido:</span>
          <span className="sheet-preview__value">{caseData.suggestedTier}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">ESI asignado:</span>
          <span className="sheet-preview__tier" style={{ background: colors.bg, color: colors.text }}>
            {caseData.confirmedESI}
          </span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Tiempo de revisión:</span>
          <span className="sheet-preview__value">{formatDuration(caseData.reviewSeconds)}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Confirmado:</span>
          <span className="sheet-preview__value">{new Date(caseData.confirmedAt).toLocaleString('es-ES')}</span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Resumen (EN):</span>
          <span className="sheet-preview__value">{caseData.englishSummary}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Lectura (ES):</span>
          <span className="sheet-preview__value">{caseData.spanishReadback}</span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">Firma de enfermería:</span>
          <span className="sheet-preview__value sheet-preview__signed">✓ Confirmado (demostración)</span>
        </div>
      </div>
    </div>
  )
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}
