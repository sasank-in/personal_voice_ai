import { useRecorder } from '../hooks/useRecorder'
import { formatTime } from '../services/format'
import { MicIcon, StopIcon } from './Icons'

interface Props {
  maxSeconds: number
  disabled?: boolean
  label?: string
  variant?: 'compact' | 'large'
  onComplete: (recording: Blob) => void
}

export function AudioRecorder({ maxSeconds, disabled, label = 'Record', variant = 'compact', onComplete }: Props) {
  const { status, elapsed, error, start, stop } = useRecorder(maxSeconds, onComplete)
  const recording = status === 'recording'
  const requesting = status === 'requesting'

  if (variant === 'large') {
    return (
      <div className="recorder-large">
        <button
          type="button"
          className={`record-button${recording ? ' is-recording' : ''}`}
          aria-label={recording ? 'Stop' : label}
          disabled={disabled || requesting}
          onClick={recording ? stop : start}
        >
          {recording ? <StopIcon size={26} /> : <MicIcon size={28} />}
        </button>
        <p className="record-caption" role={recording ? 'timer' : undefined}>
          {recording ? (
            <>
              <span className="live-dot" aria-hidden="true" />
              Recording {formatTime(elapsed)} / {formatTime(maxSeconds)}
            </>
          ) : requesting ? (
            'Waiting for microphone permission…'
          ) : (
            label
          )}
        </p>
        {error && <p className="field-error" role="alert">{error}</p>}
      </div>
    )
  }

  return (
    <div className="recorder-compact">
      {recording && (
        <span className="recording-pill" role="timer">
          <span className="live-dot" aria-hidden="true" />
          {formatTime(elapsed)} / {formatTime(maxSeconds)}
        </span>
      )}
      <button
        type="button"
        className={`icon-button ${recording ? 'icon-button-danger' : 'icon-button-soft'}`}
        aria-label={recording ? 'Stop' : label}
        title={recording ? 'Stop and send' : label}
        disabled={disabled || requesting}
        onClick={recording ? stop : start}
      >
        {recording ? <StopIcon size={18} /> : <MicIcon size={20} />}
      </button>
      {error && <p className="recorder-error" role="alert">{error}</p>}
    </div>
  )
}
