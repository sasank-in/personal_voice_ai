import { Alert } from '../components/Alert'
import { ChatIcon, MicIcon, PlusIcon, SpeakerIcon } from '../components/Icons'
import type { Conversation, User, VoiceProfile } from '../types'

interface Props {
  user: User
  voice: VoiceProfile | null
  voicesLoaded: boolean
  conversations: Conversation[] | null
  loadError: string | null
  onNewConversation: () => void
}

const STEPS = [
  { icon: MicIcon, title: 'Record your voice', text: 'Read a short passage for 10 to 15 seconds.' },
  { icon: ChatIcon, title: 'Ask anything', text: 'Type, or press the microphone and speak.' },
  { icon: SpeakerIcon, title: 'Hear it in your voice', text: 'Every reply is spoken back in your cloned voice.' },
]

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function Dashboard({ user, voice, voicesLoaded, conversations, loadError, onNewConversation }: Props) {
  const name = user.email.split('@')[0]
  const recent = conversations?.slice(0, 5) ?? []

  return (
    <div className="stack-lg">
      <header className="page-header">
        <div>
          <h1 className="page-title">Welcome, {name}</h1>
          <p className="page-subtitle">Talk with your assistant, and hear it answer in your own voice.</p>
        </div>
        <button type="button" className="button button-primary" onClick={onNewConversation}>
          <PlusIcon size={16} />
          New conversation
        </button>
      </header>

      {loadError && <Alert tone="error">{loadError}</Alert>}

      <div className="grid-2">
        <section className="card">
          <div className="card-icon"><MicIcon size={20} /></div>
          <h2 className="card-title">Your voice</h2>
          {!voicesLoaded ? (
            <p className="muted">Loading…</p>
          ) : voice ? (
            <>
              <p className="muted">
                Replies are spoken as <strong className="text-strong">{voice.name}</strong>.
              </p>
              <div className="card-actions">
                <span className="badge badge-success">Ready</span>
                <a className="button button-secondary button-small" href="#/settings">Manage</a>
              </div>
            </>
          ) : (
            <>
              <p className="muted">Record a short sample to hear replies in your own voice. Until then, replies are text only.</p>
              <div className="card-actions">
                <a className="button button-primary button-small" href="#/enroll">Create your voice</a>
              </div>
            </>
          )}
        </section>

        <section className="card">
          <div className="card-icon"><ChatIcon size={20} /></div>
          <h2 className="card-title">Recent conversations</h2>
          {conversations === null ? (
            <p className="muted">Loading…</p>
          ) : recent.length === 0 ? (
            <p className="muted">No conversations yet. Start one to begin.</p>
          ) : (
            <ul className="recent-list">
              {recent.map((conversation) => (
                <li key={conversation.id}>
                  <a href={`#/conversation/${conversation.id}`}>
                    <span className="recent-title">{conversation.title}</span>
                    <span className="recent-date">{formatDate(conversation.updated_at)}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {voicesLoaded && !voice && (
        <section>
          <h2 className="section-title">How it works</h2>
          <ol className="steps">
            {STEPS.map(({ icon: StepIcon, title, text }, index) => (
              <li key={title} className="step">
                <span className="step-number">{index + 1}</span>
                <StepIcon size={20} />
                <h3>{title}</h3>
                <p className="muted">{text}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}
