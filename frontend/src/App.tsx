import { useCallback, useEffect, useState } from 'react'
import { ConversationPage } from './pages/Conversation'
import { Dashboard } from './pages/Dashboard'
import { Enrollment } from './pages/Enrollment'
import { Login } from './pages/Login'
import { Settings } from './pages/Settings'
import { api, setUnauthorizedHandler } from './services/api'
import type { User } from './types'

function currentPath(): string {
  return window.location.hash.slice(1) || '/'
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [path, setPath] = useState(currentPath)

  useEffect(() => {
    const handler = () => setPath(currentPath())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setChecking(false))
  }, [])

  const navigate = useCallback((next: string) => {
    window.location.hash = next
  }, [])

  async function logout() {
    await api.logout().catch(() => undefined)
    setUser(null)
  }

  if (checking) return null
  if (!user) return <Login onLogin={setUser} />

  const conversationId = path.match(/^\/conversation\/([\w-]+)$/)?.[1]

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">Personal Voice AI</a>
        <nav>
          <a href="#/settings">Settings</a>
          <button type="button" className="button subtle" onClick={logout}>Log out</button>
        </nav>
      </header>
      <main className="content">
        {conversationId ? (
          <ConversationPage key={conversationId} conversationId={conversationId} />
        ) : path === '/enroll' ? (
          <Enrollment user={user} navigate={navigate} />
        ) : path === '/settings' ? (
          <Settings user={user} onUserChange={setUser} />
        ) : (
          <Dashboard navigate={navigate} />
        )}
      </main>
    </div>
  )
}
