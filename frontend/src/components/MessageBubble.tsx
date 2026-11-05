import { AudioPlayer } from './AudioPlayer'
import { Logo, RetryIcon, SpeakerIcon, Spinner } from './Icons'
import type { Message } from '../types'

interface Props {
  message: Message
  userInitial: string
  autoPlay: boolean
  audioError?: string
  generating: boolean
  canGenerateAudio: boolean
  onGenerateAudio: () => void
  onPlaybackEnded: () => void
}

export function MessageBubble({
  message,
  userInitial,
  autoPlay,
  audioError,
  generating,
  canGenerateAudio,
  onGenerateAudio,
  onPlaybackEnded,
}: Props) {
  const fromUser = message.role === 'user'
  // Any reply without audio can be spoken: a text-only turn, a failed attempt, or deleted audio.
  const canSpeak = !fromUser && !message.audio && (canGenerateAudio || generating)

  return (
    <article className={`message ${fromUser ? 'message-user' : 'message-assistant'}`}>
      {fromUser ? (
        <span className="avatar avatar-small" aria-hidden="true">{userInitial}</span>
      ) : (
        <Logo size={30} />
      )}
      <div className="message-body">
        <p className="message-author">{fromUser ? 'You' : 'Assistant'}</p>
        <div className="message-bubble">
          <p className="message-text">{message.content}</p>
        </div>
        {message.audio && (
          <AudioPlayer key={message.audio.id} url={message.audio.url} autoPlay={autoPlay} onEnded={onPlaybackEnded} />
        )}
        {!message.audio && audioError && !generating && (
          <p className="field-error" role="alert">Voice generation failed: {audioError}</p>
        )}
        {canSpeak && (
          <button
            type="button"
            className="button button-ghost button-small message-action"
            disabled={generating || !canGenerateAudio}
            onClick={onGenerateAudio}
          >
            {generating ? <Spinner size={14} /> : audioError ? <RetryIcon size={15} /> : <SpeakerIcon size={15} />}
            {generating ? 'Generating voice…' : audioError ? 'Retry voice' : 'Play in my voice'}
          </button>
        )}
      </div>
    </article>
  )
}
