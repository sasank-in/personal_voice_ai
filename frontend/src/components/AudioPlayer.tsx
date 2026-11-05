import { useEffect, useRef, useState } from 'react'
import { pauseAllAudio } from '../services/audioPlayback'
import { formatTime } from '../services/format'
import { PauseIcon, PlayIcon } from './Icons'

interface Props {
  url: string
  autoPlay?: boolean
  label?: string
  onEnded?: () => void
}

export function AudioPlayer({ url, autoPlay, label = 'AI voice', onEnded }: Props) {
  const ref = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!autoPlay) return
    // Browsers may refuse autoplay; the play button remains available.
    ref.current?.play().catch(() => onEnded?.())
    // Only the initial play is automatic.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPlay])

  function toggle() {
    const audio = ref.current
    if (!audio) return
    if (audio.paused) audio.play().catch(() => setFailed(true))
    else audio.pause()
  }

  if (failed) {
    return <p className="field-error" role="alert">This audio could not be played.</p>
  }

  return (
    <div className="player">
      <button type="button" className="player-button" aria-label={playing ? 'Pause' : 'Play'} onClick={toggle}>
        {playing ? <PauseIcon size={16} /> : <PlayIcon size={16} />}
      </button>
      <input
        className="player-seek"
        type="range"
        aria-label="Playback position"
        min={0}
        max={duration || 0}
        step={0.05}
        value={Math.min(time, duration || 0)}
        onChange={(event) => {
          const audio = ref.current
          if (audio) audio.currentTime = Number(event.target.value)
        }}
      />
      <span className="player-time">
        {formatTime(time)} / {formatTime(duration)}
      </span>
      <span className="badge badge-soft">{label}</span>
      <audio
        ref={ref}
        src={url}
        preload="metadata"
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
        onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
        onPlay={(event) => {
          pauseAllAudio(event.currentTarget)
          setPlaying(true)
        }}
        onPause={() => {
          setPlaying(false)
          onEnded?.()
        }}
        onEnded={() => {
          setPlaying(false)
          onEnded?.()
        }}
        onError={() => {
          setFailed(true)
          onEnded?.()
        }}
      />
    </div>
  )
}
