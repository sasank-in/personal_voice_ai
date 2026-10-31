import type { VoiceProfile } from '../types'

const KEY = 'selected-voice-profile'

export function saveSelectedVoice(id: string): void {
  try {
    localStorage.setItem(KEY, id)
  } catch {
    // Only a convenience: the first ready voice is used without it.
  }
}

function loadSelectedVoice(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function pickVoice(voices: VoiceProfile[]): VoiceProfile | null {
  const ready = voices.filter((voice) => voice.status === 'ready')
  return ready.find((voice) => voice.id === loadSelectedVoice()) ?? ready[0] ?? null
}
