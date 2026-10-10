import React, { useState, useEffect, useCallback } from 'react'
import PatientPage from './pages/PatientPage.jsx'
import StaffSignIn from './pages/StaffSignIn.jsx'
import QRPanel from './components/QRPanel.jsx'
import './styles/preview.css'

// ── Minimal SPA router (pathname-based) ──
// /        → Patient intake (public)
// /nurse   → Staff sign-in → Nurse workstation (protected)
// /qr      → QR code panel (organizer/staff)
function useRoute() {
  const [path, setPath] = useState(() => window.location.pathname)
  useEffect(() => {
    const handler = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])
  const navigate = useCallback((to) => {
    window.history.pushState({}, '', to)
    setPath(to)
    window.scrollTo(0, 0)
  }, [])
  return { path, navigate }
}

export default function App() {
  const { path, navigate } = useRoute()

  if (path === '/nurse') {
    return <StaffSignIn navigate={navigate} />
  }
  if (path === '/qr') {
    return <QRPanel navigate={navigate} />
  }
  // Default: patient intake
  return <PatientPage />
}
