import { useEffect, useState } from 'react'
import { VoiceEnrollment } from '../components/VoiceEnrollment'
import { api } from '../services/api'
import type { Languages, User } from '../types'

export function Enrollment({ user, onCreated }: { user: User; onCreated: () => void }) {
  const [languages, setLanguages] = useState<Languages | null>(null)

  useEffect(() => {
    api.languages().then(setLanguages).catch(() => setLanguages({ 'en-IN': 'English' }))
  }, [])

  return (
    <div className="stack-lg">
      <header className="page-header">
        <div>
          <h1 className="page-title">Create your voice</h1>
          <p className="page-subtitle">Record a short, clean sample. It takes about a minute.</p>
        </div>
      </header>
      {languages && <VoiceEnrollment languages={languages} defaultLanguage={user.language} onCreated={onCreated} />}
    </div>
  )
}
