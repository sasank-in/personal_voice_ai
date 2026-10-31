import { useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import { pickVoice, saveSelectedVoice } from '../services/selectedVoice'
import type { Languages, User, VoiceProfile } from '../types'

interface Props {
  user: User
  onUserChange: (user: User) => void
}

export function Settings({ user, onUserChange }: Props) {
  const [languages, setLanguages] = useState<Languages>({})
  const [voices, setVoices] = useState<VoiceProfile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function fail(caught: unknown) {
    setNotice(null)
    setError(caught instanceof ApiError ? caught.message : 'That did not work. Please try again.')
  }

  useEffect(() => {
    Promise.all([api.languages(), api.listVoices()])
      .then(([languageMap, voiceList]) => {
        setLanguages(languageMap)
        setVoices(voiceList)
        setSelected(pickVoice(voiceList)?.id ?? null)
      })
      .catch(fail)
  }, [])

  async function changeLanguage(language: string) {
    setError(null)
    try {
      onUserChange(await api.updateLanguage(language))
      setNotice('Language updated.')
    } catch (caught) {
      fail(caught)
    }
  }

  function selectVoice(id: string) {
    saveSelectedVoice(id)
    setSelected(id)
    setNotice('Voice selected.')
  }

  async function deleteVoice(voice: VoiceProfile) {
    if (!window.confirm(`Delete "${voice.name}"? This also deletes the cloned voice from Sarvam.`)) return
    setError(null)
    try {
      await api.deleteVoice(voice.id)
      const remaining = voices.filter((v) => v.id !== voice.id)
      setVoices(remaining)
      setSelected(pickVoice(remaining)?.id ?? null)
      setNotice('Voice profile deleted.')
    } catch (caught) {
      fail(caught)
    }
  }

  async function deleteAudio() {
    if (!window.confirm('Delete all generated audio? Message text is kept.')) return
    setError(null)
    try {
      const { deleted } = await api.deleteAllAudio()
      setNotice(`Deleted ${deleted} audio file${deleted === 1 ? '' : 's'}.`)
    } catch (caught) {
      fail(caught)
    }
  }

  return (
    <div className="stack">
      <h1>Settings</h1>
      {notice && <p className="status" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      <section className="card stack">
        <h2>Conversation language</h2>
        <label className="field">
          Used for transcription, replies and speech
          <select value={user.language} onChange={(event) => changeLanguage(event.target.value)}>
            {Object.entries(languages).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </label>
      </section>

      <section className="card stack">
        <h2>Voice profiles</h2>
        {voices.length === 0 && <p className="hint">No voice profiles yet.</p>}
        <ul className="list">
          {voices.map((voice) => (
            <li key={voice.id} className="row-between">
              <label className="radio">
                <input
                  type="radio"
                  name="voice"
                  disabled={voice.status !== 'ready'}
                  checked={selected === voice.id}
                  onChange={() => selectVoice(voice.id)}
                />
                <span>{voice.name}{voice.status !== 'ready' && ` (${voice.status})`}</span>
              </label>
              <button type="button" className="button subtle" onClick={() => deleteVoice(voice)}>Delete</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="card stack">
        <h2>Audio retention</h2>
        <p className="hint">
          Voice samples and your spoken messages are not kept after processing. Generated replies are stored
          privately until you delete them or the conversation.
        </p>
        <div>
          <button type="button" className="button" onClick={deleteAudio}>Delete all generated audio</button>
        </div>
      </section>
    </div>
  )
}
