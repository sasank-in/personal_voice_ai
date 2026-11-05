import { type FormEvent, useEffect, useState } from 'react'
import { Alert } from '../components/Alert'
import { AuthLayout } from '../components/AuthLayout'
import { Spinner } from '../components/Icons'
import { ApiError, api } from '../services/api'
import type { User } from '../types'

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [signupEnabled, setSignupEnabled] = useState(false)

  useEffect(() => {
    api.authOptions().then((options) => setSignupEnabled(options.signup_enabled)).catch(() => undefined)
  }, [])

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
    <AuthLayout title="Welcome back" subtitle="Log in to continue your conversations.">
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span className="field-label">Email</span>
          <input className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Password</span>
          <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button type="submit" className="button button-primary button-block" disabled={busy}>
          {busy && <Spinner />}
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      {signupEnabled && (
        <p className="auth-switch">
          New here? <a href="#/signup">Create an account</a>
        </p>
      )}
    </AuthLayout>
  )
}
