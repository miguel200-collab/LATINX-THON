import React, { useState } from 'react'
import PatientPage from './pages/PatientPage.jsx'
import NursePage from './pages/NursePage.jsx'
import PreviewNav from './components/PreviewNav.jsx'
import './styles/preview.css'

export default function App() {
  const [view, setView] = useState('patient')

  return (
    <div className="app-root">
      <PreviewNav view={view} setView={setView} />
      {view === 'patient' ? <PatientPage /> : <NursePage />}
    </div>
  )
}
