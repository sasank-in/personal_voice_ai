import { useEffect, useRef, useState } from 'react'

interface Props {
  url: string
  autoPlay?: boolean
  onEnded?: () => void
}

export function AudioPlayer({ url, autoPlay, onEnded }: Props) {
  const ref = useRef<HTMLAudioElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!autoPlay) return
    // Browsers may refuse autoplay; the visible controls remain available.
    ref.current?.play().catch(() => onEnded?.())
    // Only the initial play is automatic.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPlay])

  if (failed) {
    return <p className="error" role="alert">This audio could not be played.</p>
  }

  return (
    <div className="player">
      <audio
        ref={ref}
        src={url}
        controls
        preload="metadata"
        onEnded={onEnded}
        onError={() => {
          setFailed(true)
          onEnded?.()
        }}
      />
      <span className="hint">AI-generated speech</span>
    </div>
  )
}
