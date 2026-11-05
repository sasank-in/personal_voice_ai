import { useCallback, useEffect, useState } from 'react'
import { Logo, MenuIcon } from './components/Icons'
import { Sidebar } from './components/Sidebar'
import { ConversationPage } from './pages/Conversation'
import { Dashboard } from './pages/Dashboard'
import { Enrollment } from './pages/Enrollment'
import { Login } from './pages/Login'
import { Settings } from './pages/Settings'
import { Signup } from './pages/Signup'
import { api, setUnauthorizedHandler } from './services/api'
import { pickVoice } from './services/selectedVoice'
import type { Conversation, User, VoiceProfile } from './types'

function currentPath(): string {
  return window.location.hash.slice(1) || '/'
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [path, setPath] = useState(currentPath)
  const [navOpen, setNavOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[] | null>(null)
  const [voices, setVoices] = useState<VoiceProfile[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const handler = () => {
      setPath(currentPath())
      setNavOpen(false)
    }
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  // Clears the previous account's data, so another account never sees it.
  const signOut = useCallback(() => {
    setUser(null)
    setConversations(null)
    setVoices(null)
    setLoadError(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(signOut)
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setChecking(false))
  }, [signOut])

  const refreshConversations = useCallback(() => {
    api.listConversations().then(setConversations).catch(() => setLoadError('Could not load your conversations.'))
  }, [])

  const refreshVoices = useCallback(() => {
    api.listVoices().then(setVoices).catch(() => setLoadError('Could not load your voice profiles.'))
  }, [])

  const userId = user?.id
  useEffect(() => {
    if (!userId) return
    refreshConversations()
    refreshVoices()
  }, [userId, refreshConversations, refreshVoices])

  const navigate = useCallback((next: string) => {
    window.location.hash = next
  }, [])

  // After any logout, show the login page rather than whatever page the address points to.
  const loggedOut = useCallback(() => {
    window.location.hash = '/'
    signOut()
  }, [signOut])

  async function logout() {
    await api.logout().catch(() => undefined)
    loggedOut()
  }

  async function newConversation() {
    try {
      const conversation = await api.createConversation()
      setConversations((current) => [conversation, ...(current ?? [])])
      navigate(`/conversation/${conversation.id}`)
    } catch {
      setLoadError('Could not start a conversation.')
    }
  }

  async function deleteConversation(id: string) {
    if (!window.confirm('Delete this conversation and its audio? This cannot be undone.')) return
    try {
      await api.deleteConversation(id)
      setConversations((current) => current?.filter((c) => c.id !== id) ?? null)
      if (path === `/conversation/${id}`) navigate('/')
    } catch {
      setLoadError('Could not delete that conversation.')
    }
  }

  if (checking) return <div className="boot" aria-busy="true" />
  if (!user) return path === '/signup' ? <Signup onSignup={setUser} /> : <Login onLogin={setUser} />

  const conversationId = path.match(/^\/conversation\/([\w-]+)$/)?.[1]
  const voice = voices ? pickVoice(voices) : null
  const conversation = conversations?.find((c) => c.id === conversationId)

  return (
    <div className="shell">
      <Sidebar
        user={user}
        path={path}
        open={navOpen}
        conversations={conversations}
        voice={voice}
        onClose={() => setNavOpen(false)}
        onNewConversation={newConversation}
        onDeleteConversation={deleteConversation}
        onLogout={logout}
      />
      <div className="main">
        <header className="mobile-bar">
          <button type="button" className="icon-button icon-button-ghost" aria-label="Open menu" onClick={() => setNavOpen(true)}>
            <MenuIcon />
          </button>
          <a className="brand" href="#/">
            <Logo size={26} />
            <span>Personal Voice AI</span>
          </a>
        </header>
        {conversationId ? (
          <main className="page page-chat">
            <ConversationPage
              key={conversationId}
              conversationId={conversationId}
              title={conversation?.title ?? 'Conversation'}
              userInitial={user.email.slice(0, 1).toUpperCase()}
              voice={voice}
              voicesLoaded={voices !== null}
              onChanged={refreshConversations}
            />
          </main>
        ) : (
          <main className="page">
            <div className="page-inner">
              {path === '/enroll' ? (
                <Enrollment
                  user={user}
                  onCreated={() => {
                    refreshVoices()
                    navigate('/')
                  }}
                />
              ) : path === '/settings' ? (
                <Settings
                  user={user}
                  voices={voices}
                  onUserChange={setUser}
                  onVoicesChanged={refreshVoices}
                  onLoggedOut={loggedOut}
                />
              ) : (
                <Dashboard
                  user={user}
                  voice={voice}
                  voicesLoaded={voices !== null}
                  conversations={conversations}
                  loadError={loadError}
                  onNewConversation={newConversation}
                />
              )}
            </div>
          </main>
        )}
      </div>
    </div>
  )
}
