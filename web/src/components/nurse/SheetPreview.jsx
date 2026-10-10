import React from 'react'
import { TIER_COLORS, tierLabel, tierLabelShort } from '../../mockData.js'
import { makeT } from '../../i18n.js'

// ════════════════════════════════════════════════════════════════
// Sheet preview — intake sheet and confirmed sheet
// Uses frontend sample content, labeled as samples.
// Patient words and Spanish read-back stay in their original language.
// ════════════════════════════════════════════════════════════════

export function IntakeSheetPreview({ caseData, lang = 'en' }) {
  const t = makeT(lang, 'nurse')
  const colors = TIER_COLORS[caseData.suggestedTier]
  return (
    <div className="sheet-preview">
      <div className="sheet-preview__header">
        <span className="sheet-preview__title">{t('intakeSheet')}</span>
        <span className="sheet-preview__sample-tag">{t('sampleTag')}</span>
      </div>
      <div className="sheet-preview__body">
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetId')}</span>
          <span className="sheet-preview__value">{caseData.id} ({caseData.label})</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetPatient')}</span>
          <span className="sheet-preview__value">{caseData.patient.age} {t('yearsOld')}, {caseData.patient.sex}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetSuggestedTier')}</span>
          <span className="sheet-preview__tier" style={{ background: colors.bg, color: colors.text }}>
            {caseData.suggestedTier}
          </span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetChief')}</span>
          <span className="sheet-preview__value">{caseData.chart.chiefComplaint?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetLocation')}</span>
          <span className="sheet-preview__value">{caseData.chart.location?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetOnset')}</span>
          <span className="sheet-preview__value">{caseData.chart.onset?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetQuality')}</span>
          <span className="sheet-preview__value">{caseData.chart.quality?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetAggravating')}</span>
          <span className="sheet-preview__value">{caseData.chart.aggravating?.extracted || '—'}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetAssociated')}</span>
          <span className="sheet-preview__value">{caseData.chart.associated?.extracted || '—'}</span>
        </div>
        {caseData.redFlags.length > 0 && (
          <>
            <div className="sheet-preview__divider" />
            <div className="sheet-preview__row sheet-preview__row--col">
              <span className="sheet-preview__label sheet-preview__label--red">{t('sheetRedFlags')}</span>
              <span className="sheet-preview__value">{caseData.redFlags.join(', ')}</span>
            </div>
          </>
        )}
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetOfficialEsi')}</span>
          <span className="sheet-preview__value sheet-preview__blank">{t('sheetEsiPlaceholder')}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetSignature')}</span>
          <span className="sheet-preview__value sheet-preview__blank">{t('sheetSignaturePlaceholder')}</span>
        </div>
      </div>
    </div>
  )
}

export function ConfirmedSheetPreview({ caseData, lang = 'en' }) {
  const t = makeT(lang, 'nurse')
  const colors = TIER_COLORS[caseData.confirmedESI]
  return (
    <div className="sheet-preview sheet-preview--confirmed">
      <div className="sheet-preview__header">
        <span className="sheet-preview__title">{t('confirmedSheet')}</span>
        <span className="sheet-preview__sample-tag">{t('sampleTag')}</span>
      </div>
      <div className="sheet-preview__body">
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetId')}</span>
          <span className="sheet-preview__value">{caseData.id} ({caseData.label})</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetPatient')}</span>
          <span className="sheet-preview__value">{caseData.patient.age} {t('yearsOld')}, {caseData.patient.sex}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetSuggestedTier')}</span>
          <span className="sheet-preview__value">{caseData.suggestedTier}</span>
        </div>
        <div className="sheet-preview__row">
          <span className="sheet-preview__label">{t('sheetAssignedEsi')}</span>
          <span className="sheet-preview__tier" style={{ background: colors.bg, color: colors.text }}>
            {caseData.confirmedESI}
          </span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetReviewTime')}</span>
          <span className="sheet-preview__value">{formatDuration(caseData.reviewSeconds)}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetConfirmed')}</span>
          <span className="sheet-preview__value">{new Date(caseData.confirmedAt).toLocaleString(lang === 'es' ? 'es-ES' : 'en-US')}</span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetEnSummary')}</span>
          <span className="sheet-preview__value">{caseData.englishSummary}</span>
        </div>
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetEsReadback')}</span>
          <span className="sheet-preview__value">{caseData.spanishReadback}</span>
        </div>
        <div className="sheet-preview__divider" />
        <div className="sheet-preview__row sheet-preview__row--col">
          <span className="sheet-preview__label">{t('sheetNurseSig')}</span>
          <span className="sheet-preview__value sheet-preview__signed">{t('sheetSignedDemo')}</span>
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
