import React, { useState, useRef, useEffect } from 'react'

export default function VoiceNotePlayer({ url, duration, isOwn = false, timestamp, lang = 'es' }) {
  const audioRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onTime = () => setProgress(audio.currentTime / (audio.duration || 1))
    const onEnd = () => { setIsPlaying(false); setProgress(0) }
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('ended', onEnd)
    return () => {
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('ended', onEnd)
    }
  }, [])

  const toggle = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      audio.play()
      setIsPlaying(true)
    }
  }

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const playAria = lang === 'es' ? 'Reproducir nota de voz' : 'Play voice note'
  const pauseAria = lang === 'es' ? 'Pausar' : 'Pause'

  // Generate static waveform bars
  const bars = Array.from({ length: 28 }, (_, i) => {
    const seed = (i * 37 + 13) % 100
    return 20 + (seed % 60) / 100 * 80
  })

  return (
    <div className={`voice-note ${isOwn ? 'voice-note--own' : ''}`}>
      <audio ref={audioRef} src={url} preload="metadata" />
      <button
        className="voice-note__play"
        onClick={toggle}
        aria-label={isPlaying ? pauseAria : playAria}
      >
        {isPlaying ? (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>
      <div className="voice-note__body">
        <div className="voice-note__waveform">
          {bars.map((h, i) => (
            <div
              key={i}
              className="voice-note__bar"
              style={{
                height: `${h}%`,
                opacity: i / bars.length <= progress ? 1 : 0.4,
              }}
            />
          ))}
        </div>
        <span className="voice-note__duration">{formatTime(duration)}</span>
      </div>
      {timestamp && <span className="voice-note__time">{timestamp}</span>}
    </div>
  )
}
