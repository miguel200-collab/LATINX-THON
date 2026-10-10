import React from 'react'

// ════════════════════════════════════════════════════════════════
// Reusable English / Español toggle.
// variant: 'light' = light text on dark bg (WhatsApp header, nurse titlebar)
//          'dark'  = dark text on light bg (staff sign-in card, QR panel)
// ════════════════════════════════════════════════════════════════

export default function LanguageToggle({ lang, setLang, variant = 'light' }) {
  return (
    <div className={`lang-toggle lang-toggle--${variant}`} role="group" aria-label="Language / Idioma">
      <button
        className={`lang-toggle__btn ${lang === 'en' ? 'lang-toggle__btn--active' : ''}`}
        onClick={() => setLang('en')}
        aria-pressed={lang === 'en'}
      >
        English
      </button>
      <span className="lang-toggle__sep" aria-hidden="true">/</span>
      <button
        className={`lang-toggle__btn ${lang === 'es' ? 'lang-toggle__btn--active' : ''}`}
        onClick={() => setLang('es')}
        aria-pressed={lang === 'es'}
      >
        Español
      </button>
    </div>
  )
}
