import { useEffect, useState } from 'react'
import { Alert } from './Alert'
import { AudioPlayer } from './AudioPlayer'
import { AudioRecorder } from './AudioRecorder'
import { ShieldIcon, Spinner } from './Icons'
import { ApiError, api } from '../services/api'
import { saveSelectedVoice } from '../services/selectedVoice'
import type { Languages, VoiceProfile } from '../types'

const MAX_SAMPLE_SECONDS = 30

const PASSAGE =
  'The morning was calm and bright. I made a cup of tea, opened the window, and listened to the city waking up. ' +
  'Today I want to plan my week, learn something new, and call a friend I have not spoken to in a while.'

const TIPS = [
  'Record 10 to 15 seconds in a quiet room.',
  'Only one person should be speaking.',
  'Keep the microphone at a steady distance.',
  'Avoid music, echo and background voices.',
]

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

  const ready = Boolean(sample) && consent && name.trim().length > 0

  return (
    <div className="enroll">
      <div className="stack">
        <section className="card step-card">
          <header className="step-header">
            <span className={`step-badge${consent && name.trim() ? ' is-done' : ''}`}>1</span>
            <div>
              <h2 className="card-title">Details and permission</h2>
              <p className="muted">Name this voice and confirm you may clone it.</p>
            </div>
          </header>
          <div className="form-row">
            <label className="field">
              <span className="field-label">Profile name</span>
              <input className="input" value={name} maxLength={100} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Language you will record in</span>
              <select className="input" value={language} onChange={(event) => setLanguage(event.target.value)}>
                {Object.entries(languages).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="consent">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
            <span>
              This is my own voice, or I have the owner's explicit permission. I have the right to record,
              process and clone it, and to use it to generate new speech.
            </span>
          </label>
        </section>

        <section className={`card step-card${consent ? '' : ' is-locked'}`}>
          <header className="step-header">
            <span className={`step-badge${sample ? ' is-done' : ''}`}>2</span>
            <div>
              <h2 className="card-title">Record a sample</h2>
              <p className="muted">
                {consent ? 'Press the microphone and read the passage below in your natural voice.' : 'Confirm permission in step 1 first.'}
              </p>
            </div>
          </header>
          {language === 'en-IN' && <blockquote className="passage">{PASSAGE}</blockquote>}
          <AudioRecorder
            variant="large"
            maxSeconds={MAX_SAMPLE_SECONDS}
            disabled={!consent || creating}
            label={sample ? 'Record again' : 'Start recording'}
            onComplete={acceptSample}
          />
        </section>

        <section className={`card step-card${sample ? '' : ' is-locked'}`}>
          <header className="step-header">
            <span className="step-badge">3</span>
            <div>
              <h2 className="card-title">Review and create</h2>
              <p className="muted">{sample ? 'Listen back. If it sounds clear, create your voice.' : 'Your recording will appear here.'}</p>
            </div>
          </header>
          {previewUrl && <AudioPlayer key={previewUrl} url={previewUrl} label="Your sample" />}
          {progress !== null && (
            <div className="progress" aria-label="Upload progress">
              <progress value={progress} max={1} />
            </div>
          )}
          {error && <Alert tone="error">{error}</Alert>}
          <div className="card-actions">
            <button type="button" className="button button-primary" disabled={!ready || creating} onClick={submit}>
              {creating && <Spinner />}
              {creating ? (progress !== null ? 'Uploading…' : 'Creating your voice…') : 'Create voice profile'}
            </button>
          </div>
        </section>
      </div>

      <aside className="card enroll-tips">
        <h2 className="card-title">For the best result</h2>
        <ul className="check-list">
          {TIPS.map((tip) => <li key={tip}>{tip}</li>)}
        </ul>
        <div className="note">
          <ShieldIcon size={18} />
          <p>Your recording is sent to Sarvam to create the voice and is not kept by this app.</p>
        </div>
      </aside>
    </div>
  )
}
