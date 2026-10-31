export interface User {
  id: string
  email: string
  language: string
}

export interface VoiceProfile {
  id: string
  name: string
  provider: string
  status: 'pending' | 'ready' | 'failed' | 'deleted'
  language: string
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Audio {
  id: string
  url: string
  content_type: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  audio: Audio | null
}

export interface AudioError {
  code: string
  message: string
  stage: string
  retryable: boolean
}

export interface Turn {
  user_message: Message
  assistant_message: Message
  audio: Audio | null
  audio_error: AudioError | null
}

export type Languages = Record<string, string>
