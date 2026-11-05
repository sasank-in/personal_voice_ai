import { type FormEvent, useState } from 'react'
import { Alert } from '../components/Alert'
import { AuthLayout } from '../components/AuthLayout'
import { Spinner } from '../components/Icons'
import { ApiError, api } from '../services/api'
import type { User } from '../types'

const MIN_PASSWORD_LENGTH = 8

export function Signup({ onSignup }: { onSignup: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const user = await api.signup(email.trim(), password)
      window.location.hash = '/'
      onSignup(user)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not create the account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="It takes a minute. You can add your voice right after.">
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span className="field-label">Email</span>
          <input className="input" type="email" autoComplete="email" required maxLength={320} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Password</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={1024}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <span className="field-hint">At least {MIN_PASSWORD_LENGTH} characters.</span>
        </label>
        <label className="field">
          <span className="field-label">Confirm password</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={1024}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button type="submit" className="button button-primary button-block" disabled={busy}>
          {busy && <Spinner />}
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="auth-switch">
        Already have an account? <a href="#/login">Log in</a>
      </p>
    </AuthLayout>
  )
}
