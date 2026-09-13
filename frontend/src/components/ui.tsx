import type { ReactNode } from 'react'
import type { StreamStatus } from '../lib/api'
import { STATUS_LABEL } from '../lib/format'

export function StatusPill({ status }: { status: StreamStatus }) {
  let cls = 'pill-neutral'
  switch (status) {
    case 'active':
      cls = 'pill-green'
      break
    case 'due_soon':
      cls = 'pill-amber'
      break
    case 'overdue':
    case 'charge_missed':
    case 'amc_lapsed':
      cls = 'pill-red'
      break
    case 'stopped':
    case 'cancelled':
    case 'dismissed':
      cls = 'pill-grey'
      break
    case 'needs_confirm':
      cls = 'pill-blue'
      break
    case 'one_time':
      cls = 'pill-neutral'
      break
  }
  return <span className={`pill ${cls}`}>{STATUS_LABEL[status] ?? status}</span>
}

export function ErrorMsg({ children }: { children: ReactNode }) {
  if (!children) return null
  return (
    <div className="msg msg-error" role="alert">
      {children}
    </div>
  )
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="loading">{text}</div>
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  )
}

export function Sources({ sources }: { sources: string[] }) {
  if (!sources || sources.length === 0) return <span className="muted">—</span>
  return (
    <>
      {sources.map((s) => (
        <span key={s} className="tag">
          {s}
        </span>
      ))}
    </>
  )
}

export function NoCompany() {
  return (
    <div className="card">
      <Empty title="No company selected">
        Create a company on the Upload page to get started.
      </Empty>
    </div>
  )
}
