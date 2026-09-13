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
  charge_missed: 'Payment missed',
  stopped: 'Stopped',
  cancelled: 'Cancelled',
  amc_lapsed: 'AMC expired',
  one_time: 'One-time',
  needs_confirm: 'Is this a subscription?',
  dismissed: 'Hidden',
}

/** Where a payment was seen, in plain words. */
export const SOURCE_LABEL: Record<string, string> = {
  bank: 'Bank statement',
  card: 'Card statement',
  tally: 'Tally',
  manual: 'Added by hand',
  personal: 'Personal account',
}
export function sourceLabel(s: string): string {
  return SOURCE_LABEL[s] ?? humanize(s)
}

/** 0–100 confidence → High / Likely / Guess. */
export function confidenceLabel(c: number | null | undefined): string {
  if (c === null || c === undefined) return '—'
  if (c >= 80) return 'High'
  if (c >= 50) return 'Likely'
  return 'Guess'
}

/** Plain-English fallbacks for engine flag keys when `flags_human` is missing. */
export const FLAG_LABELS: Record<string, string> = {
  rcm_gst_payable: 'You pay 18% GST on this yourself (reverse charge)',
  price_hike: 'Price went up',
  price_drop: 'Price came down',
  cycle_from_invoice: 'Cycle read from the invoice',
  supplier_changed: 'Supplier changed',
  paid_from_personal: 'Paid from a personal account',
  amount_varies: 'Amount changes each time',
  catch_up_payment: 'Catch-up payment',
  tally_unpaid: 'Invoice booked in Tally, not yet paid',
  booked_not_paid: 'Invoice booked in Tally, not yet paid',
  foreign_vendor: 'Foreign vendor (paid in another currency)',
}
export function flagLabel(f: string): string {
  return FLAG_LABELS[f] ?? humanize(f)
}

const DIGEST_DAYS: Record<string, string> = {
  mon: 'Monday',
  tue: 'Tuesday',
  wed: 'Wednesday',
  thu: 'Thursday',
  fri: 'Friday',
  sat: 'Saturday',
  sun: 'Sunday',
}
export function dayLabel(d: string | null | undefined): string {
  if (!d) return 'Off'
  return DIGEST_DAYS[d] ?? d
}

export const CATEGORY_LABELS: Record<string, string> = {
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
