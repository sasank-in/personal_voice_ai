import type {
  Audio,
  Conversation,
  Languages,
  Message,
  Turn,
  User,
  VoiceProfile,
} from '../types'

const BASE = '/api/v1'
const TIMEOUT_MS = 180_000

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly stage: string | null
  readonly retryable: boolean

  constructor(status: number, code: string, message: string, stage: string | null = null, retryable = false) {
    super(message)
    this.status = status
    this.code = code
    this.stage = stage
    this.retryable = retryable
  }
}

let onUnauthorized: () => void = () => {}

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

function toApiError(status: number, body: unknown): ApiError {
  const error = (body as { error?: Partial<ApiError> } | null)?.error
  if (error?.code) {
    return new ApiError(status, error.code, error.message ?? 'Something went wrong.', error.stage ?? null, error.retryable ?? false)
  }
  return new ApiError(status, 'unexpected_error', 'Something went wrong. Please try again.', null, status >= 500)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(BASE + path, {
      ...init,
      credentials: 'same-origin',
      signal: controller.signal,
      headers: init.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the server. Please try again.', null, true)
  } finally {
    window.clearTimeout(timer)
  }

  if (response.status === 204) return undefined as T

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') onUnauthorized()
    throw toApiError(response.status, body)
  }
  return body as T
}

interface UploadOptions {
  onProgress?: (fraction: number) => void
  onUploaded?: () => void
}

// XMLHttpRequest because fetch cannot report upload progress.
function upload<T>(path: string, form: FormData, options: UploadOptions = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + path)
    xhr.timeout = TIMEOUT_MS
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) options.onProgress?.(event.loaded / event.total)
    }
    xhr.upload.onload = () => options.onUploaded?.()
    xhr.onerror = () => reject(new ApiError(0, 'upload_failed', 'The upload failed. Please try again.', 'uploading', true))
    xhr.ontimeout = () => reject(new ApiError(0, 'timeout', 'The request timed out. Please try again.', null, true))
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // Handled below as an unexpected error.
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T)
        return
      }
      if (xhr.status === 401) onUnauthorized()
      reject(toApiError(xhr.status, body))
    }
    xhr.send(form)
  })
}

export function recordingFilename(blob: Blob): string {
  return blob.type.includes('mp4') ? 'recording.m4a' : 'recording.webm'
}

export const api = {
  login: (email: string, password: string) =>
    request<User>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  me: () => request<User>('/me'),
  updateLanguage: (language: string) =>
    request<User>('/me', { method: 'PATCH', body: JSON.stringify({ language }) }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>('/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  languages: () => request<Languages>('/languages'),

  listVoices: () => request<VoiceProfile[]>('/voices'),
  deleteVoice: (id: string) => request<void>(`/voices/${id}`, { method: 'DELETE' }),
  createVoice: (name: string, language: string, sample: Blob, options: UploadOptions) => {
    const form = new FormData()
    form.append('name', name)
    form.append('language', language)
    form.append('consent_confirmed', 'true')
    form.append('file', sample, recordingFilename(sample))
    return upload<VoiceProfile>('/voices', form, options)
  },

  listConversations: () => request<Conversation[]>('/conversations'),
  createConversation: () =>
    request<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({}) }),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: 'DELETE' }),
  listMessages: (id: string) => request<Message[]>(`/conversations/${id}/messages`),
  sendText: (id: string, content: string, voiceProfileId: string | null) =>
    request<Turn>(`/conversations/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, voice_profile_id: voiceProfileId, generate_audio: voiceProfileId !== null }),
    }),
  sendAudio: (id: string, recording: Blob, voiceProfileId: string | null, options: UploadOptions) => {
    const form = new FormData()
    form.append('file', recording, recordingFilename(recording))
    if (voiceProfileId) form.append('voice_profile_id', voiceProfileId)
    return upload<Turn>(`/conversations/${id}/audio`, form, options)
  },
  retryAudio: (conversationId: string, messageId: string, voiceProfileId: string) =>
    request<Audio>(`/conversations/${conversationId}/messages/${messageId}/audio`, {
      method: 'POST',
      body: JSON.stringify({ voice_profile_id: voiceProfileId }),
    }),
  deleteAllAudio: () => request<{ deleted: number }>('/audio', { method: 'DELETE' }),
}
