import { useEffect, useRef } from 'react'
import { MessageBubble } from './MessageBubble'
import type { Message } from '../types'

interface Props {
  messages: Message[]
  autoPlayAudioId: string | null
  audioErrors: Record<string, string>
  canRetryAudio: boolean
  onRetryAudio: (messageId: string) => void
  onPlaybackEnded: () => void
}

export function ChatWindow({ messages, autoPlayAudioId, audioErrors, canRetryAudio, onRetryAudio, onPlaybackEnded }: Props) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length])

  return (
    <div className="chat" aria-live="polite">
      {messages.length === 0 && <p className="hint chat-empty">Type a message or press Speak to begin.</p>}
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          autoPlay={message.audio !== null && message.audio.id === autoPlayAudioId}
          audioError={audioErrors[message.id]}
          canRetryAudio={canRetryAudio}
          onRetryAudio={() => onRetryAudio(message.id)}
          onPlaybackEnded={onPlaybackEnded}
        />
      ))}
      <div ref={endRef} />
    </div>
  )
}
