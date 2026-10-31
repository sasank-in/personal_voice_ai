import { type FormEvent, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { User } from '../types'

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onLogin(await api.login(email.trim(), password))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not log in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <form className="card stack" onSubmit={submit}>
        <h1>Personal Voice AI</h1>
        <label className="field">
          Email
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          Password
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="button primary" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
      </form>
    </main>
  )
}
