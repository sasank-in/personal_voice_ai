import { useRecorder } from '../hooks/useRecorder'

interface Props {
  maxSeconds: number
  disabled?: boolean
  label?: string
  onComplete: (recording: Blob) => void
}

export function AudioRecorder({ maxSeconds, disabled, label = 'Record', onComplete }: Props) {
  const { status, elapsed, error, start, stop } = useRecorder(maxSeconds, onComplete)
  const recording = status === 'recording'

  return (
    <div className="recorder">
      <button
        type="button"
        className={recording ? 'button danger' : 'button primary'}
        disabled={disabled || status === 'requesting'}
        onClick={recording ? stop : start}
      >
        {recording ? 'Stop' : status === 'requesting' ? 'Waiting for microphone…' : label}
      </button>
      {recording && (
        <span className="recorder-time" role="timer">
          <span className="recording-dot" aria-hidden="true" />
          {Math.floor(elapsed)}s of {maxSeconds}s
        </span>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  )
}
