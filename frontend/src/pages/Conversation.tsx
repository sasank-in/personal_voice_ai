import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { AudioRecorder } from '../components/AudioRecorder'
import { ChatWindow } from '../components/ChatWindow'
import { ApiError, api } from '../services/api'
import { pickVoice } from '../services/selectedVoice'
import type { Message, Turn, VoiceProfile } from '../types'

type Phase = 'idle' | 'uploading' | 'processing' | 'playing'

const MAX_UTTERANCE_SECONDS = 29

const FAILED_STAGE: Record<string, string> = {
  uploading: 'Upload failed',
  transcribing: 'Transcription failed',
  generating_text: 'The assistant could not reply',
  generating_audio: 'Voice generation failed',
}

const PHASE_LABEL: Partial<Record<Phase, string>> = {
  uploading: 'Uploading your recording…',
  processing: 'Working on a reply…',
}

interface Failure {
  message: string
  retry?: () => void
}

function describe(caught: unknown): string {
  if (!(caught instanceof ApiError)) return 'Something went wrong.'
  const stage = caught.stage ? FAILED_STAGE[caught.stage] : undefined
  return stage ? `${stage}: ${caught.message}` : caught.message
}

export function ConversationPage({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [voice, setVoice] = useState<VoiceProfile | null>(null)
  const [draft, setDraft] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoPlayAudioId, setAutoPlayAudioId] = useState<string | null>(null)
  const [audioErrors, setAudioErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    let active = true
    Promise.all([api.listMessages(conversationId), api.listVoices()])
      .then(([history, voices]) => {
        if (!active) return
        setMessages(history)
        setVoice(pickVoice(voices))
      })
      .catch((caught) => active && setFailure({ message: describe(caught) }))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [conversationId])

  function applyTurn(turn: Turn) {
    setMessages((current) => [
      ...current,
      turn.user_message,
      { ...turn.assistant_message, audio: turn.audio },
    ])
    if (turn.audio_error) {
      setAudioErrors((current) => ({ ...current, [turn.assistant_message.id]: turn.audio_error!.message }))
    }
    if (turn.audio) {
      setAutoPlayAudioId(turn.audio.id)
      setPhase('playing')
    } else {
      setPhase('idle')
    }
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

  async function retryAudio(messageId: string) {
    if (!voice) return
    setFailure(null)
    setPhase('processing')
    try {
      const audio = await api.retryAudio(conversationId, messageId, voice.id)
      setMessages((current) => current.map((m) => (m.id === messageId ? { ...m, audio } : m)))
      setAudioErrors(({ [messageId]: _resolved, ...rest }) => rest)
      setAutoPlayAudioId(audio.id)
      setPhase('playing')
    } catch (caught) {
      setPhase('idle')
      setFailure({ message: describe(caught) })
    }
  }

  const finishPlayback = useCallback(() => {
    setPhase((current) => (current === 'playing' ? 'idle' : current))
  }, [])

  function submit(event: FormEvent) {
    event.preventDefault()
    const content = draft.trim()
    if (content) void sendText(content)
  }

  const busy = phase === 'uploading' || phase === 'processing'

  return (
    <div className="conversation">
      <p className="hint">
        <a href="#/">← All conversations</a>
        {' · '}
        {voice ? `Replying in ${voice.name}` : 'Text replies only: no voice profile yet'}
      </p>

      {loading ? (
        <p className="hint">Loading…</p>
      ) : (
        <ChatWindow
          messages={messages}
          autoPlayAudioId={autoPlayAudioId}
          audioErrors={audioErrors}
          canRetryAudio={voice !== null && !busy}
          onRetryAudio={retryAudio}
          onPlaybackEnded={finishPlayback}
        />
      )}

      <div className="composer">
        {PHASE_LABEL[phase] && <p className="status" role="status">{PHASE_LABEL[phase]}</p>}
        {failure && (
          <div className="inline-error" role="alert">
            <p className="error">{failure.message}</p>
            {failure.retry && (
              <button type="button" className="button" onClick={failure.retry}>Try again</button>
            )}
          </div>
        )}
        <form className="composer-row" onSubmit={submit}>
          <input
            aria-label="Message"
            placeholder="Type a message"
            value={draft}
            maxLength={8000}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" className="button" disabled={busy || !draft.trim()}>Send</button>
          <AudioRecorder
            maxSeconds={MAX_UTTERANCE_SECONDS}
            disabled={busy}
            label="Speak"
            onComplete={sendRecording}
          />
        </form>
      </div>
    </div>
  )
}
