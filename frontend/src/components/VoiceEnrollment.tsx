import { useEffect, useState } from 'react'
import { AudioRecorder } from './AudioRecorder'
import { ApiError, api } from '../services/api'
import { saveSelectedVoice } from '../services/selectedVoice'
import type { Languages, VoiceProfile } from '../types'

const MAX_SAMPLE_SECONDS = 30

interface Props {
  languages: Languages
  defaultLanguage: string
  onCreated: (profile: VoiceProfile) => void
}

export function VoiceEnrollment({ languages, defaultLanguage, onCreated }: Props) {
  const [name, setName] = useState('My voice')
  const [language, setLanguage] = useState(defaultLanguage)
  const [consent, setConsent] = useState(false)
  const [sample, setSample] = useState<Blob | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  function acceptSample(recording: Blob) {
    setSample(recording)
    setPreviewUrl(URL.createObjectURL(recording))
  }

  async function submit() {
    if (!sample) return
    setError(null)
    setCreating(true)
    setProgress(0)
    try {
      const profile = await api.createVoice(name.trim(), language, sample, {
        onProgress: setProgress,
        onUploaded: () => setProgress(null),
      })
      saveSelectedVoice(profile.id)
      onCreated(profile)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not create the voice profile.')
    } finally {
      setCreating(false)
      setProgress(null)
    }
  }

  return (
    <div className="stack">
      <section className="card">
        <h2>Before you record</h2>
        <ul className="tips">
          <li>Record 10 to 15 seconds in a quiet room.</li>
          <li>Only one person should be speaking.</li>
          <li>Keep the microphone at a consistent distance.</li>
          <li>Speak naturally and clearly.</li>
          <li>Avoid music, echo and background conversations.</li>
        </ul>
      </section>

      <section className="card stack">
        <h2>Your details</h2>
        <label className="field">
          Profile name
          <input value={name} maxLength={100} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="field">
          Language you will record in
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            {Object.entries(languages).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </label>
        <label className="consent">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          <span>
            This is my own voice, or I have the owner's explicit permission. I have the right to record,
            process and clone it, and to use it to generate new speech.
          </span>
        </label>
      </section>

      <section className="card stack">
        <h2>Voice sample</h2>
        <AudioRecorder
          maxSeconds={MAX_SAMPLE_SECONDS}
          disabled={!consent || creating}
          label={sample ? 'Record again' : 'Start recording'}
          onComplete={acceptSample}
        />
        {!consent && <p className="hint">Confirm the permission statement above to start recording.</p>}
        {previewUrl && (
          <div className="stack">
            <p className="hint">Listen back before you continue.</p>
            <audio src={previewUrl} controls />
          </div>
        )}
        {progress !== null && <progress value={progress} max={1} aria-label="Upload progress" />}
        {error && <p className="error" role="alert">{error}</p>}
        <div>
          <button
            type="button"
            className="button primary"
            disabled={!sample || !consent || creating || !name.trim()}
            onClick={submit}
          >
            {creating ? (progress !== null ? 'Uploading…' : 'Creating your voice…') : 'Create voice profile'}
          </button>
        </div>
      </section>
    </div>
  )
}
