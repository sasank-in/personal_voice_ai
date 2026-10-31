import { useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import { pickVoice } from '../services/selectedVoice'
import type { Conversation, VoiceProfile } from '../types'

export function Dashboard({ navigate }: { navigate: (path: string) => void }) {
  const [voices, setVoices] = useState<VoiceProfile[] | null>(null)
  const [conversations, setConversations] = useState<Conversation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.listVoices(), api.listConversations()])
      .then(([voiceList, conversationList]) => {
        setVoices(voiceList)
        setConversations(conversationList)
      })
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : 'Could not load your data.'))
  }, [])

  async function startConversation() {
    try {
      const conversation = await api.createConversation()
      navigate(`/conversation/${conversation.id}`)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not start a conversation.')
    }
  }

  async function removeConversation(id: string) {
    try {
      await api.deleteConversation(id)
      setConversations((current) => current?.filter((c) => c.id !== id) ?? null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not delete that conversation.')
    }
  }

  const voice = voices ? pickVoice(voices) : null

  return (
    <div className="stack">
      {error && <p className="error" role="alert">{error}</p>}
      <section className="card stack">
        <h2>Voice profile</h2>
        {voices === null ? (
          <p className="hint">Loading…</p>
        ) : voice ? (
          <p>Replies will use <strong>{voice.name}</strong>.</p>
        ) : (
          <p>You don't have a voice profile yet. Replies will be text only until you create one.</p>
        )}
        <div>
          <button type="button" className={voice ? 'button' : 'button primary'} onClick={() => navigate('/enroll')}>
            Create voice profile
          </button>
        </div>
      </section>

      <section className="card stack">
        <div className="row-between">
          <h2>Conversations</h2>
          <button type="button" className="button primary" onClick={startConversation}>New conversation</button>
        </div>
        {conversations === null ? (
          <p className="hint">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="hint">No conversations yet.</p>
        ) : (
          <ul className="list">
            {conversations.map((conversation) => (
              <li key={conversation.id} className="row-between">
                <a href={`#/conversation/${conversation.id}`}>{conversation.title}</a>
                <button type="button" className="button subtle" onClick={() => removeConversation(conversation.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
