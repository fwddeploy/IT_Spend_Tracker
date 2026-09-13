import type { Cycle, StreamStatus } from './api'

export function rupees(n: number | null | undefined, opts: { decimals?: boolean } = {}): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const decimals = opts.decimals ?? false
  return (
    '₹' +
    n.toLocaleString('en-IN', {
      minimumFractionDigits: decimals ? 2 : 0,
      maximumFractionDigits: decimals ? 2 : 0,
    })
  )
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-04-10" → "10 Apr 2026". Accepts ISO datetimes too. */
export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s)
  if (!m) return s
  return `${parseInt(m[3], 10)} ${MONTHS[parseInt(m[2], 10) - 1]} ${m[1]}`
}

/** ISO datetime → "2 Sep 2026, 14:05" (local time). */
export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return fmtDate(s)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${hh}:${mm}`
}

/** "2026-10" → "Oct 2026" */
export function fmtMonth(s: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(s)
  if (!m) return s
  return `${MONTHS[parseInt(m[2], 10) - 1]} ${m[1]}`
}

export function shortMonth(s: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(s)
  if (!m) return s
  return MONTHS[parseInt(m[2], 10) - 1]
}

export function todayISO(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null
  const t = new Date(iso + 'T00:00:00').getTime()
  const now = new Date(todayISO() + 'T00:00:00').getTime()
  return Math.round((t - now) / 86400000)
}

export const CYCLE_LABEL: Record<Cycle, string> = {
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-yearly',
  yearly: 'Yearly',
  biennial: 'Every 2 years',
  triennial: 'Every 3 years',
  irregular: 'Irregular',
  custom: 'Custom',
}

export const STATUS_LABEL: Record<StreamStatus, string> = {
  active: 'Active',
  due_soon: 'Due soon',
  overdue: 'Overdue',
  charge_missed: 'Charge missed',
  stopped: 'Stopped',
  cancelled: 'Cancelled',
  amc_lapsed: 'AMC lapsed',
  one_time: 'One-time',
  needs_confirm: 'Needs confirm',
  dismissed: 'Dismissed',
}

const CATEGORY_LABELS: Record<string, string> = {
  cad: 'CAD / design tools',
  erp: 'ERP / accounts',
  office: 'Office / email',
  security: 'Antivirus / security',
  cloud: 'Cloud / hosting',
  domain: 'Domain / website',
  communication: 'Communication',
  hr: 'HR / payroll',
  design: 'Design / creative',
  compliance: 'Compliance / tax',
  amc: 'IT support / AMC',
  telecom: 'Broadband / telecom',
  dev: 'Developer tools',
  other: 'Other',
}

export function humanize(s: string | null | undefined): string {
  if (!s) return '—'
  if (CATEGORY_LABELS[s]) return CATEGORY_LABELS[s]
  return s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}
