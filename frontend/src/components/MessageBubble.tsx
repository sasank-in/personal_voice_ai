import { AudioPlayer } from './AudioPlayer'
import type { Message } from '../types'

interface Props {
  message: Message
  autoPlay: boolean
  audioError?: string
  canRetryAudio: boolean
  onRetryAudio: () => void
  onPlaybackEnded: () => void
}

export function MessageBubble({ message, autoPlay, audioError, canRetryAudio, onRetryAudio, onPlaybackEnded }: Props) {
  return (
    <article className={`bubble ${message.role}`}>
      <p className="bubble-role">{message.role === 'user' ? 'You' : 'Assistant'}</p>
      <p className="bubble-text">{message.content}</p>
      {message.audio && (
        <AudioPlayer key={message.audio.id} url={message.audio.url} autoPlay={autoPlay} onEnded={onPlaybackEnded} />
      )}
      {!message.audio && audioError && (
        <div className="inline-error" role="alert">
          <p className="error">Voice generation failed: {audioError}</p>
          {canRetryAudio && (
            <button type="button" className="button" onClick={onRetryAudio}>Retry voice</button>
          )}
        </div>
      )}
    </article>
  )
}
