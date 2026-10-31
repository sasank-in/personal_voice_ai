import { useCallback, useEffect, useRef, useState } from 'react'

export type RecorderStatus = 'idle' | 'requesting' | 'recording'

const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']

function recorderError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'Microphone permission was denied. Allow microphone access in your browser settings and try again.'
  }
  if (name === 'NotFoundError') return 'No microphone was found.'
  if (name === 'NotReadableError') return 'The microphone is being used by another application.'
  return 'Could not start recording in this browser.'
}

export function useRecorder(maxSeconds: number, onComplete: (recording: Blob) => void) {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)
  const discardRef = useRef(false)
  const onCompleteRef = useRef(onComplete)

  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  const release = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current)
    timerRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }, [])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setElapsed(0)
    setStatus('requesting')
    try {
      // Permission is requested here, only after the user presses record.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mimeType = MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      const chunks: Blob[] = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data)
      }
      recorder.onstop = () => {
        release()
        setStatus('idle')
        if (!discardRef.current && chunks.length > 0) {
          onCompleteRef.current(new Blob(chunks, { type: recorder.mimeType }))
        }
      }
      recorderRef.current = recorder
      discardRef.current = false
      recorder.start()
      setStatus('recording')

      const startedAt = Date.now()
      timerRef.current = window.setInterval(() => {
        const seconds = (Date.now() - startedAt) / 1000
        setElapsed(seconds)
        if (seconds >= maxSeconds) stop()
      }, 200)
    } catch (caught) {
      release()
      setStatus('idle')
      setError(recorderError(caught))
    }
  }, [maxSeconds, release, stop])

  useEffect(
    () => () => {
      discardRef.current = true
      stop()
      release()
    },
    [release, stop],
  )

  return { status, elapsed, error, start, stop }
}
