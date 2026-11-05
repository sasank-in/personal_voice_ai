import type { ReactNode } from 'react'
import { AlertIcon, CheckIcon } from './Icons'

interface Props {
  tone: 'error' | 'success' | 'info'
  children: ReactNode
  action?: ReactNode
}

export function Alert({ tone, children, action }: Props) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {tone === 'success' ? <CheckIcon size={18} /> : <AlertIcon size={18} />}
      <div className="alert-body">{children}</div>
      {action}
    </div>
  )
}
