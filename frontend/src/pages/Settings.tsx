import { type FormEvent, type ReactNode, useEffect, useState } from 'react'
import { Alert } from '../components/Alert'
import { PlusIcon, TrashIcon } from '../components/Icons'
import { ApiError, api } from '../services/api'
import { pickVoice, saveSelectedVoice } from '../services/selectedVoice'
import type { Languages, User, VoiceProfile } from '../types'

interface Props {
  user: User
  voices: VoiceProfile[] | null
  onUserChange: (user: User) => void
  onVoicesChanged: () => void
  onLoggedOut: () => void
}

function Section({ title, description, danger, children }: { title: string; description: string; danger?: boolean; children: ReactNode }) {
  return (
    <section className={`settings-section${danger ? ' is-danger' : ''}`}>
      <div className="settings-intro">
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      <div className="card">{children}</div>
    </section>
  )
}

const STATUS_BADGE: Record<string, string> = { ready: 'badge-success', pending: 'badge-warning', failed: 'badge-danger' }

export function Settings({ user, voices, onUserChange, onVoicesChanged, onLoggedOut }: Props) {
  const [languages, setLanguages] = useState<Languages>({})
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.languages().then(setLanguages).catch(() => setError('Could not load languages.'))
  }, [])

  const selected = voices ? (pickVoice(voices)?.id ?? null) : null

  function fail(caught: unknown) {
    setNotice(null)
    setError(caught instanceof ApiError ? caught.message : 'That did not work. Please try again.')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function succeed(message: string) {
    setError(null)
    setNotice(message)
  }

  async function changeLanguage(language: string) {
    try {
      onUserChange(await api.updateLanguage(language))
      succeed('Language updated.')
    } catch (caught) {
      fail(caught)
    }
  }

  function selectVoice(id: string) {
    saveSelectedVoice(id)
    // Reloading the voices re-renders every view that shows the selected voice.
    onVoicesChanged()
    succeed('Voice selected.')
  }

  async function deleteVoice(voice: VoiceProfile) {
    if (!window.confirm(`Delete "${voice.name}"? This also deletes the cloned voice from Sarvam.`)) return
    try {
      await api.deleteVoice(voice.id)
      onVoicesChanged()
      succeed('Voice profile deleted.')
    } catch (caught) {
      fail(caught)
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      fail(new ApiError(400, 'password_mismatch', 'The new passwords do not match.'))
      return
    }
    try {
      await api.changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      succeed('Password changed. Other devices have been logged out.')
    } catch (caught) {
      fail(caught)
    }
  }

  async function logoutEverywhere() {
    if (!window.confirm('Log out on every device, including this one?')) return
    try {
      await api.logoutEverywhere()
      onLoggedOut()
    } catch (caught) {
      fail(caught)
    }
  }

  async function deleteAudio() {
    if (!window.confirm('Delete all generated audio? Message text is kept.')) return
    try {
      const { deleted } = await api.deleteAllAudio()
      succeed(`Deleted ${deleted} audio file${deleted === 1 ? '' : 's'}.`)
    } catch (caught) {
      fail(caught)
    }
  }

  async function deleteAccount(event: FormEvent) {
    event.preventDefault()
    const warning =
      'Permanently delete your account? This deletes your conversations, generated audio and cloned voices, including at Sarvam. This cannot be undone.'
    if (!window.confirm(warning)) return
    try {
      await api.deleteAccount(deletePassword)
      onLoggedOut()
    } catch (caught) {
      fail(caught)
    }
  }

  return (
    <div className="stack-lg">
      <header className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Manage your account, voices and data.</p>
        </div>
      </header>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <Section title="Profile" description="Your account and the language your assistant uses.">
        <div className="stack">
          <div className="field">
            <span className="field-label">Email</span>
            <p className="text-strong">{user.email}</p>
          </div>
          <label className="field">
            <span className="field-label">Conversation language</span>
            <select className="input" value={user.language} onChange={(event) => changeLanguage(event.target.value)}>
              {Object.entries(languages).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
            <span className="field-hint">Used for transcription, replies and speech.</span>
          </label>
        </div>
      </Section>

      <Section title="Voices" description="Choose which cloned voice speaks your replies.">
        {voices === null ? (
          <p className="muted">Loading…</p>
        ) : voices.length === 0 ? (
          <p className="muted">No voice profiles yet.</p>
        ) : (
          <ul className="voice-list">
            {voices.map((voice) => (
              <li key={voice.id} className="voice-row">
                <label className="radio">
                  <input
                    type="radio"
                    name="voice"
                    disabled={voice.status !== 'ready'}
                    checked={selected === voice.id}
                    onChange={() => selectVoice(voice.id)}
                  />
                  <span className="voice-name">{voice.name}</span>
                  <span className="voice-meta">{languages[voice.language] ?? voice.language}</span>
                </label>
                <span className={`badge ${STATUS_BADGE[voice.status] ?? ''}`}>{voice.status}</span>
                <button
                  type="button"
                  className="icon-button icon-button-ghost"
                  aria-label={`Delete ${voice.name}`}
                  title="Delete voice"
                  onClick={() => deleteVoice(voice)}
                >
                  <TrashIcon size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="card-actions">
          <a className="button button-secondary button-small" href="#/enroll">
            <PlusIcon size={15} />
            Add a voice
          </a>
        </div>
      </Section>

      <Section title="Password" description="Changing it logs you out on your other devices.">
        <form className="form" onSubmit={changePassword}>
          <label className="field">
            <span className="field-label">Current password</span>
            <input className="input" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
          </label>
          <div className="form-row">
            <label className="field">
              <span className="field-label">New password</span>
              <input className="input" type="password" autoComplete="new-password" required minLength={8} maxLength={1024} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
              <span className="field-hint">At least 8 characters.</span>
            </label>
            <label className="field">
              <span className="field-label">Confirm new password</span>
              <input className="input" type="password" autoComplete="new-password" required minLength={8} maxLength={1024} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </label>
          </div>
          <div className="card-actions">
            <button type="submit" className="button button-primary">Change password</button>
          </div>
        </form>
      </Section>

      <Section title="Devices" description="End every session where you are logged in.">
        <div className="row-between">
          <p className="muted">Logs out all devices, including this one.</p>
          <button type="button" className="button button-secondary" onClick={logoutEverywhere}>Log out everywhere</button>
        </div>
      </Section>

      <Section title="Audio" description="Voice samples and your spoken messages are not kept after processing.">
        <div className="row-between">
          <p className="muted">Generated replies are stored privately until you delete them or the conversation.</p>
          <button type="button" className="button button-secondary" onClick={deleteAudio}>Delete all generated audio</button>
        </div>
      </Section>

      <Section title="Delete account" description="Permanently remove your account and everything in it." danger>
        <form className="form" onSubmit={deleteAccount}>
          <p className="muted">
            This deletes your conversations, generated audio and cloned voices, including the copies held by Sarvam.
            It cannot be undone.
          </p>
          <label className="field">
            <span className="field-label">Password</span>
            <input className="input" type="password" autoComplete="current-password" required value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} />
          </label>
          <div className="card-actions">
            <button type="submit" className="button button-danger">Delete my account</button>
          </div>
        </form>
      </Section>
    </div>
  )
}
