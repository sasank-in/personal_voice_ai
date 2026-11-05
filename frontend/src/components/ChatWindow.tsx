import { useEffect, useRef } from 'react'
import { Logo, MicIcon } from './Icons'
import { MessageBubble } from './MessageBubble'
import type { Message } from '../types'

const SUGGESTIONS = [
  'Explain how vector databases work, briefly.',
  'Give me three ideas for a weekend trip.',
  'Help me plan my day in five steps.',
]

interface Props {
  messages: Message[]
  userInitial: string
  pending: string | null
  autoPlayAudioId: string | null
  audioErrors: Record<string, string>
  generatingId: string | null
  canGenerateAudio: boolean
  onGenerateAudio: (messageId: string) => void
  onPlaybackEnded: () => void
  onSuggestion: (text: string) => void
}

export function ChatWindow({
  messages,
  userInitial,
  pending,
  autoPlayAudioId,
  audioErrors,
  generatingId,
  canGenerateAudio,
  onGenerateAudio,
  onPlaybackEnded,
  onSuggestion,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [messages.length, pending])

  if (messages.length === 0 && !pending) {
    return (
      <div className="chat-empty">
        <span className="chat-empty-icon"><MicIcon size={26} /></span>
        <h2>Start the conversation</h2>
        <p className="muted">Type a message, or press the microphone and speak.</p>
        <div className="suggestions">
          {SUGGESTIONS.map((text) => (
            <button key={text} type="button" className="suggestion" onClick={() => onSuggestion(text)}>
              {text}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="messages" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          userInitial={userInitial}
          autoPlay={message.audio !== null && message.audio.id === autoPlayAudioId}
          audioError={audioErrors[message.id]}
          generating={generatingId === message.id}
          canGenerateAudio={canGenerateAudio}
          onGenerateAudio={() => onGenerateAudio(message.id)}
          onPlaybackEnded={onPlaybackEnded}
        />
      ))}
      {pending && (
        <article className="message message-assistant" aria-busy="true">
          <Logo size={30} />
          <div className="message-body">
            <p className="message-author">Assistant</p>
            <div className="message-bubble message-pending">
              <span className="typing" aria-hidden="true"><i /><i /><i /></span>
              <span className="muted">{pending}</span>
            </div>
          </div>
        </article>
      )}
      <div ref={endRef} />
    </div>
  )
}
