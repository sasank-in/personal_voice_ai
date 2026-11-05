import type { ReactNode } from 'react'
import { CheckIcon, Logo } from './Icons'

const FEATURES = [
  'Speak naturally and get answers back in seconds',
  'Hear every reply in a voice cloned from yours',
  'Your recordings are processed, not kept',
]

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-aside">
        <div className="brand brand-inverse">
          <Logo size={36} />
          <span>Personal Voice AI</span>
        </div>
        <div className="auth-pitch">
          <h2>An assistant that answers in your own voice.</h2>
          <ul className="auth-features">
            {FEATURES.map((feature) => (
              <li key={feature}>
                <span className="auth-check"><CheckIcon size={14} /></span>
                {feature}
              </li>
            ))}
          </ul>
        </div>
        <p className="auth-footnote">Only clone a voice you have the right to use.</p>
      </aside>
      <main className="auth-main">
        <div className="auth-panel">
          <div className="brand auth-mobile-brand">
            <Logo size={32} />
            <span>Personal Voice AI</span>
          </div>
          <h1 className="auth-title">{title}</h1>
          <p className="auth-subtitle">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  )
}
