import { useEffect, useState } from 'react'
import { VoiceEnrollment } from '../components/VoiceEnrollment'
import { api } from '../services/api'
import type { Languages, User } from '../types'

export function Enrollment({ user, navigate }: { user: User; navigate: (path: string) => void }) {
  const [languages, setLanguages] = useState<Languages | null>(null)

  useEffect(() => {
    api.languages().then(setLanguages).catch(() => setLanguages({ 'en-IN': 'English' }))
  }, [])

  return (
    <div className="stack">
      <h1>Create voice profile</h1>
      {languages && (
        <VoiceEnrollment languages={languages} defaultLanguage={user.language} onCreated={() => navigate('/')} />
      )}
    </div>
  )
}
