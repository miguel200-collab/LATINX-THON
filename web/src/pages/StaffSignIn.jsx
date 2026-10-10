import React, { useState } from 'react'
import LanguageToggle from '../components/LanguageToggle.jsx'
import NursePage from './NursePage.jsx'
import { makeT } from '../i18n.js'
import '../styles/staff-signin.css'

// ════════════════════════════════════════════════════════════════
// Staff sign-in — gate to the nurse workstation.
//
// SIMULATED ACCESS: This is a frontend-only mock. The PIN check
// below is NOT real authentication. Real protection requires
// backend auth + role verification (see explanation in the UI).
// ════════════════════════════════════════════════════════════════

const DEMO_PIN = '1234'

export default function StaffSignIn({ navigate }) {
  const [lang, setLang] = useState('en') // Nurse defaults to English
  const [authed, setAuthed] = useState(false)
  const [pin, setPin] = useState('')
  const [denied, setDenied] = useState(false)
  const t = makeT(lang, 'staff')

  const handleSignIn = (e) => {
    e.preventDefault()
    if (pin === DEMO_PIN) {
      setAuthed(true)
      setDenied(false)
    } else {
      setDenied(true)
    }
  }

  // After successful sign-in, render the nurse workstation.
  // Language state carries over so the nurse keeps her chosen language.
  if (authed) return <NursePage lang={lang} setLang={setLang} />

  return (
    <div className="staff-signin">
      <div className="staff-signin__card">
        <div className="staff-signin__lang-row">
          <LanguageToggle lang={lang} setLang={setLang} variant="dark" />
        </div>

        <div className="staff-signin__header">
          <div className="staff-signin__icon">🏥</div>
          <h1>{t('title')}</h1>
          <p className="staff-signin__subtitle">{t('subtitle')}</p>
          <div className="staff-signin__badge">{t('badgeLabel')}</div>
        </div>

        {denied ? (
          <div className="staff-signin__denied">
            <div className="staff-signin__denied-icon">⛔</div>
            <div className="staff-signin__denied-title">{t('accessDeniedTitle')}</div>
            <div className="staff-signin__denied-msg">{t('accessDeniedMsg')}</div>
            <button
              className="staff-signin__btn staff-signin__btn--primary"
              onClick={() => { setDenied(false); setPin('') }}
            >
              {t('tryAgainBtn')}
            </button>
          </div>
        ) : (
          <form className="staff-signin__form" onSubmit={handleSignIn}>
            <label className="staff-signin__label" htmlFor="staff-pin">{t('pinLabel')}</label>
            <input
              id="staff-pin"
              type="password"
              className="staff-signin__input"
              placeholder={t('pinPlaceholder')}
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              autoFocus
            />
            <button
              type="submit"
              className="staff-signin__btn staff-signin__btn--primary"
              disabled={!pin}
            >
              {t('signInBtn')}
            </button>
          </form>
        )}

        <div className="staff-signin__security-note">
          {t('securityNote')}
        </div>
        <div className="staff-signin__hint">
          {t('hint')}
        </div>

        <button className="staff-signin__back" onClick={() => navigate('/')}>
          ← {t('backBtn')}
        </button>
      </div>
    </div>
  )
}
