import React, { useState, useEffect } from 'react'
import LanguageToggle from './LanguageToggle.jsx'
import { makeT } from '../i18n.js'
import '../styles/qr-panel.css'

// ════════════════════════════════════════════════════════════════
// QR code component — generates a real QR from a URL via the
// `qrcode` library. If no URL is configured (app not published),
// shows a clearly labeled placeholder instead of a fake code.
// ════════════════════════════════════════════════════════════════

function QRCode({ value, size = 160 }) {
  const [dataUrl, setDataUrl] = useState(null)

  useEffect(() => {
    if (!value) { setDataUrl(null); return }
    let cancelled = false
    import('qrcode').then((mod) => {
      const QRCodeLib = mod.default || mod
      QRCodeLib.toDataURL(value, { width: size, margin: 1 })
        .then((url) => { if (!cancelled) setDataUrl(url) })
        .catch(() => { if (!cancelled) setDataUrl(null) })
    }).catch(() => { if (!cancelled) setDataUrl(null) })
    return () => { cancelled = true }
  }, [value, size])

  if (!value || !dataUrl) {
    return (
      <div className="qr-placeholder" style={{ width: size, height: size }} aria-label="QR code placeholder">
        <div className="qr-placeholder__grid">
          {Array.from({ length: 64 }, (_, i) => (
            <div key={i} className="qr-placeholder__cell" style={{
              opacity: ((i * 37 + 13) % 100) > 45 ? 0.12 : 0
            }} />
          ))}
        </div>
        <div className="qr-placeholder__label">QR</div>
      </div>
    )
  }

  return <img src={dataUrl} alt={`QR code for ${value}`} className="qr-code-img" width={size} height={size} />
}

// ════════════════════════════════════════════════════════════════
// QR Panel — two entry-point QR codes for the organizer/staff.
// Patient QR points to the public patient route.
// Nurse QR points to the protected nurse route.
// The nurse QR is NEVER shown on the patient screen.
// ════════════════════════════════════════════════════════════════

export default function QRPanel({ navigate }) {
  const [lang, setLang] = useState('en')
  const t = makeT(lang, 'qr')

  // Configurable base URL — set VITE_APP_BASE_URL when the app is published.
  // Until then, URLs are empty and placeholders are shown.
  const baseUrl = import.meta.env.VITE_APP_BASE_URL || ''
  const patientUrl = baseUrl ? `${baseUrl}/` : ''
  const nurseUrl = baseUrl ? `${baseUrl}/nurse` : ''

  return (
    <div className="qr-panel">
      <div className="qr-panel__header">
        <div className="qr-panel__badge">{t('demoBadge')}</div>
        <h1>{t('title')}</h1>
        <p className="qr-panel__subtitle">{t('subtitle')}</p>
        <div className="qr-panel__lang">
          <LanguageToggle lang={lang} setLang={setLang} variant="dark" />
        </div>
      </div>

      <div className="qr-panel__cards">
        {/* Patient intake QR */}
        <div className="qr-card">
          <div className="qr-card__icon">📱</div>
          <div className="qr-card__title">{t('patientTitle')}</div>
          <div className="qr-card__desc">{t('patientDesc')}</div>
          <div className="qr-card__code">
            <QRCode value={patientUrl} size={160} />
          </div>
          <div className="qr-card__url-row">
            <span className="qr-card__url-label">{t('urlLabel')}</span>
            <span className="qr-card__url-value">
              {patientUrl || t('notConfigured')}
            </span>
          </div>
          <div className="qr-card__url-row">
            <span className="qr-card__url-label">{t('routeLabel')}</span>
            <span className="qr-card__url-value">/</span>
          </div>
          {!patientUrl && (
            <div className="qr-card__placeholder-note">{t('placeholder')}</div>
          )}
        </div>

        {/* Nurse station QR */}
        <div className="qr-card qr-card--protected">
          <div className="qr-card__icon">🖥️</div>
          <div className="qr-card__title">{t('nurseTitle')}</div>
          <div className="qr-card__desc">{t('nurseDesc')}</div>
          <div className="qr-card__code">
            <QRCode value={nurseUrl} size={160} />
          </div>
          <div className="qr-card__url-row">
            <span className="qr-card__url-label">{t('urlLabel')}</span>
            <span className="qr-card__url-value">
              {nurseUrl || t('notConfigured')}
            </span>
          </div>
          <div className="qr-card__url-row">
            <span className="qr-card__url-label">{t('routeLabel')}</span>
            <span className="qr-card__url-value">/nurse</span>
          </div>
          {!nurseUrl && (
            <div className="qr-card__placeholder-note">{t('placeholder')}</div>
          )}
        </div>
      </div>

      <button className="qr-panel__back" onClick={() => navigate('/')}>
        ← {t('backBtn')}
      </button>
    </div>
  )
}
