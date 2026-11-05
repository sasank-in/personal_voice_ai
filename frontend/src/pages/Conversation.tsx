import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useState } from 'react'
import { Alert } from '../components/Alert'
import { AudioRecorder } from '../components/AudioRecorder'
import { ChatWindow } from '../components/ChatWindow'
import { SendIcon } from '../components/Icons'
import { ApiError, api } from '../services/api'
import type { Message, Turn, VoiceProfile } from '../types'

type Phase = 'idle' | 'uploading' | 'processing' | 'playing'

const MAX_UTTERANCE_SECONDS = 29

const FAILED_STAGE: Record<string, string> = {
  uploading: 'Upload failed',
  transcribing: 'Transcription failed',
  generating_text: 'The assistant could not reply',
  generating_audio: 'Voice generation failed',
}

interface Failure {
  message: string
  retry?: () => void
}

interface Props {
  conversationId: string
  title: string
  userInitial: string
  voice: VoiceProfile | null
  voicesLoaded: boolean
  onChanged: () => void
}

function describe(caught: unknown): string {
  if (!(caught instanceof ApiError)) return 'Something went wrong.'
  const stage = caught.stage ? FAILED_STAGE[caught.stage] : undefined
  return stage ? `${stage}: ${caught.message}` : caught.message
}

export function ConversationPage({ conversationId, title, userInitial, voice, voicesLoaded, onChanged }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoPlayAudioId, setAutoPlayAudioId] = useState<string | null>(null)
  const [audioErrors, setAudioErrors] = useState<Record<string, string>>({})
  const [generatingId, setGeneratingId] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .listMessages(conversationId)
      .then((history) => active && setMessages(history))
      .catch((caught) => active && setFailure({ message: describe(caught) }))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [conversationId])

  function applyTurn(turn: Turn) {
    setMessages((current) => [...current, turn.user_message, { ...turn.assistant_message, audio: turn.audio }])
    if (turn.audio_error) {
      setAudioErrors((current) => ({ ...current, [turn.assistant_message.id]: turn.audio_error!.message }))
    }
    if (turn.audio) {
      setAutoPlayAudioId(turn.audio.id)
      setPhase('playing')
    } else {
      setPhase('idle')
    }
    onChanged()
  }

  async function sendText(content: string) {
    setFailure(null)
    setPhase('processing')
    try {
      applyTurn(await api.sendText(conversationId, content, voice?.id ?? null))
      setDraft('')
    } catch (caught) {
      setPhase('idle')
      const retry = caught instanceof ApiError && caught.retryable ? () => sendText(content) : undefined
      setFailure({ message: describe(caught), retry })
    }
  }

  async function sendRecording(recording: Blob) {
    setFailure(null)
    setPhase('uploading')
    try {
      const turn = await api.sendAudio(conversationId, recording, voice?.id ?? null, {
        onUploaded: () => setPhase('processing'),
      })
      applyTurn(turn)
    } catch (caught) {
      setPhase('idle')
      const retry = caught instanceof ApiError && caught.retryable ? () => sendRecording(recording) : undefined
      setFailure({ message: describe(caught), retry })
    }
  }

  async function generateAudio(messageId: string) {
    if (!voice) return
    setFailure(null)
    setGeneratingId(messageId)
    try {
      const audio = await api.retryAudio(conversationId, messageId, voice.id)
      setMessages((current) => current.map((m) => (m.id === messageId ? { ...m, audio } : m)))
      setAudioErrors(({ [messageId]: _resolved, ...rest }) => rest)
      setAutoPlayAudioId(audio.id)
      setPhase('playing')
    } catch (caught) {
      setAudioErrors((current) => ({ ...current, [messageId]: caught instanceof ApiError ? caught.message : 'Something went wrong.' }))
    } finally {
      setGeneratingId(null)
    }
  }

  const finishPlayback = useCallback(() => {
    setPhase((current) => (current === 'playing' ? 'idle' : current))
  }, [])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    const content = draft.trim()
    if (content && !busy) void sendText(content)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  const busy = phase === 'uploading' || phase === 'processing'
  const pending = phase === 'uploading' ? 'Uploading your recording…' : phase === 'processing' ? 'Thinking…' : null

  return (
    <div className="chat">
      <header className="chat-header">
        <h1 className="chat-title" title={title}>{title}</h1>
        {voicesLoaded && (
          <span className={`chip${voice ? ' chip-success' : ''}`}>
            <span className={`status-dot${voice ? ' is-ready' : ''}`} aria-hidden="true" />
            {voice ? `Replying as ${voice.name}` : 'Text replies only'}
          </span>
        )}
      </header>

      <div className="chat-scroll">
        <div className="chat-column">
          {loading ? (
            <div className="chat-loading"><span className="skeleton" /><span className="skeleton skeleton-short" /></div>
          ) : (
            <ChatWindow
              messages={messages}
              userInitial={userInitial}
              pending={pending}
              autoPlayAudioId={autoPlayAudioId}
              audioErrors={audioErrors}
              generatingId={generatingId}
              canGenerateAudio={voice !== null && !busy && generatingId === null}
              onGenerateAudio={generateAudio}
              onPlaybackEnded={finishPlayback}
              onSuggestion={setDraft}
            />
          )}
        </div>
      </div>

      <div className="composer-wrap">
        <div className="chat-column">
          {failure && (
            <Alert
              tone="error"
              action={failure.retry && (
                <button type="button" className="button button-secondary button-small" onClick={failure.retry}>Try again</button>
              )}
            >
              {failure.message}
            </Alert>
          )}
          <form className="composer" onSubmit={submit}>
            <textarea
              className="composer-input"
              aria-label="Message"
              placeholder="Message your assistant…"
              rows={1}
              value={draft}
              maxLength={8000}
              disabled={busy}
              onKeyDown={onKeyDown}
              onChange={(event) => setDraft(event.target.value)}
            />
            <div className="composer-actions">
              <AudioRecorder maxSeconds={MAX_UTTERANCE_SECONDS} disabled={busy} label="Speak" onComplete={sendRecording} />
              <button
                type="submit"
                className="icon-button icon-button-primary"
                aria-label="Send"
                title="Send"
                disabled={busy || !draft.trim()}
              >
                <SendIcon size={18} />
              </button>
            </div>
          </form>
          <p className="composer-note">Enter to send, Shift+Enter for a new line. Replies are AI-generated.</p>
        </div>
      </div>
    </div>
  )
}
