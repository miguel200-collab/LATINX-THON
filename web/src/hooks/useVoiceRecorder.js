import { useState, useRef, useCallback, useEffect } from 'react'

// ════════════════════════════════════════════════════════════════
// Voice recorder hook — local recording only, never uploads.
// Supports: hold-to-record, tap-to-record (accessible),
//           slide-up to lock, slide-left to cancel.
// Discards recordings shorter than 0.7 seconds.
// ════════════════════════════════════════════════════════════════

const MIN_DURATION = 0.7

const ERROR_TYPES = {
  permissionDenied: {
    type: 'permissionDenied',
    title: 'Permiso de micrófono denegado',
    message: 'No se pudo acceder al micrófono. Puede continuar escribiendo sus respuestas.',
  },
  noMicrophone: {
    type: 'noMicrophone',
    title: 'No se encontró micrófono',
    message: 'No hay micrófono disponible en este dispositivo. Puede continuar escribiendo.',
  },
  unsupported: {
    type: 'unsupported',
    title: 'Navegador no compatible',
    message: 'La grabación de audio no es compatible con este navegador. Puede continuar escribiendo.',
  },
  tooShort: {
    type: 'tooShort',
    title: 'Nota de voz muy corta',
    message: 'La grabación duró menos de 0.7s. Intente de nuevo.',
  },
}

export function useVoiceRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [isLocked, setIsLocked] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)
  const [hasSupport] = useState(() =>
    typeof navigator !== 'undefined' &&
    navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === 'function' &&
    typeof window !== 'undefined' &&
    window.MediaRecorder
  )

  const mediaRecorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const startTimeRef = useRef(0)
  const resolveRef = useRef(null)
  const cancelFlagRef = useRef(false)

  const cleanupStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [])

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const resetState = useCallback(() => {
    stopTimer()
    cleanupStream()
    mediaRecorderRef.current = null
    chunksRef.current = []
    setSeconds(0)
    setIsLocked(false)
    setIsRecording(false)
  }, [stopTimer, cleanupStream])

  const startRecording = useCallback(async () => {
    if (!hasSupport) {
      setError(ERROR_TYPES.unsupported)
      return false
    }
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mr = new MediaRecorder(stream)
      mediaRecorderRef.current = mr
      chunksRef.current = []
      cancelFlagRef.current = false

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mr.onstop = () => {
        const duration = (Date.now() - startTimeRef.current) / 1000
        stopTimer()
        cleanupStream()

        if (cancelFlagRef.current) {
          resetState()
          if (resolveRef.current) { resolveRef.current(null); resolveRef.current = null }
          return
        }

        if (duration < MIN_DURATION) {
          setError(ERROR_TYPES.tooShort)
          resetState()
          if (resolveRef.current) { resolveRef.current(null); resolveRef.current = null }
          return
        }

        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const url = URL.createObjectURL(blob)
        const result = { blob, url, duration: Math.round(duration * 10) / 10 }
        resetState()
        if (resolveRef.current) { resolveRef.current(result); resolveRef.current = null }
      }

      startTimeRef.current = Date.now()
      mr.start()
      setIsRecording(true)
      setSeconds(0)
      timerRef.current = setInterval(() => {
        setSeconds((s) => s + 1)
      }, 1000)
      return true
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError(ERROR_TYPES.permissionDenied)
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setError(ERROR_TYPES.noMicrophone)
      } else {
        setError(ERROR_TYPES.unsupported)
      }
      resetState()
      return false
    }
  }, [hasSupport, resetState, stopTimer, cleanupStream])

  // Stop recording and return a Promise<{blob,url,duration} | null>
  const stopRecording = useCallback(() => {
    return new Promise((resolve) => {
      resolveRef.current = resolve
      const mr = mediaRecorderRef.current
      if (mr && mr.state !== 'inactive') {
        mr.stop()
      } else {
        resetState()
        resolve(null)
      }
    })
  }, [resetState])

  const cancelRecording = useCallback(() => {
    cancelFlagRef.current = true
    resolveRef.current = null
    const mr = mediaRecorderRef.current
    if (mr && mr.state !== 'inactive') {
      mr.stop()
    } else {
      resetState()
    }
  }, [resetState])

  const lockRecording = useCallback(() => {
    setIsLocked(true)
  }, [])

  useEffect(() => {
    return () => {
      stopTimer()
      cleanupStream()
    }
  }, [stopTimer, cleanupStream])

  return {
    isRecording,
    isLocked,
    seconds,
    error,
    hasSupport,
    startRecording,
    stopRecording,
    cancelRecording,
    lockRecording,
    clearError: () => setError(null),
  }
}
