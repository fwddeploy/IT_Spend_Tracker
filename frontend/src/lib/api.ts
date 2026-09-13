// Typed client for the IT Tracker API (docs/API.md, v1).
// Base URL is /api; in dev Vite proxies it to http://localhost:8000.

export type SourceKind = 'bank' | 'card' | 'tally' | 'generic'
export type AccountKind = 'bank' | 'card' | 'personal' | 'tally'
export type StreamType = 'subscription' | 'amc' | 'one_time' | 'prepaid'
export type Cycle =
  | 'monthly'
  | 'quarterly'
  | 'half_yearly'
  | 'yearly'
  | 'biennial'
  | 'triennial'
  | 'irregular'
  | 'custom'
export type StreamStatus =
  | 'active'
  | 'due_soon'
  | 'overdue'
  | 'charge_missed'
  | 'stopped'
  | 'cancelled'
  | 'amc_lapsed'
  | 'one_time'
  | 'needs_confirm'
  | 'dismissed'
export type StreamSource = 'bank' | 'tally' | 'manual'
export type QuestionKind = 'vendor' | 'cycle' | 'split' | 'stopped' | 'bundle'

export const CYCLES: Cycle[] = [
  'monthly',
  'quarterly',
  'half_yearly',
  'yearly',
  'biennial',
  'triennial',
  'irregular',
  'custom',
]
export const STATUSES: StreamStatus[] = [
  'active',
  'due_soon',
  'overdue',
  'charge_missed',
  'stopped',
  'cancelled',
  'amc_lapsed',
  'one_time',
  'needs_confirm',
  'dismissed',
]

export interface Company {
  id: number
  name: string
  gstin: string | null
  fy_start_month: number
  created_at: string
}

export interface ImportBatch {
  id: number
  filename: string
  source_kind: SourceKind
  account_label: string
  rows_imported: number
  rows_skipped: number
  detected_format: string | null
  created_at: string
  error?: string | null
}

export interface EngineSummary {
  occurrences: number
  streams: number
  questions_open: number
  auto_accepted: number
  needs_confirm: number
  unclassified: number
  ran_at: string
}

export interface Account {
  id: number
  label: string
  kind: AccountKind
  bank_name?: string | null
}

export interface UploadResult {
  batch: ImportBatch
  engine: EngineSummary
}

export interface StreamOut {
  id: number
  vendor_name: string
  payee_name: string | null
  product: string | null
  category: string | null
  stream_type: StreamType
  cycle: Cycle
  cycle_months: number | null
  expected_amount: number | null
  avg_amount: number | null
  monthly_equivalent: number | null
  currency: string
  last_paid_date: string | null
  next_due: string | null
  anchor_day: number | null
  status: StreamStatus
  confidence: number
  auto_renew: boolean | null
  paid_from: string | null
  owner_name: string | null
  pay_url: string | null
  reminder_on: boolean
  notes: string | null
  is_user_modified: boolean
  occurrences_count: number
  sources: StreamSource[]
  first_seen: string | null
  flags: string[]
}

export interface Occurrence {
  id: number
  date: string
  amount_paid: number
  amount_gross: number | null
  taxable: number | null
  gst: number | null
  tds: number | null
  fees: number | null
  currency: string
  fx_amount: number | null
  payment_mode: string | null
  invoice_no: string | null
  period_from: string | null
  period_to: string | null
  sources: string[]
  raw_description: string | null
}

// amount_history shape is not pinned in the contract; we accept the most likely
// form ({date, amount}) and tolerate a bare number list.
export type AmountHistoryEntry = { date?: string | null; amount: number } | number

export interface StreamDetail extends StreamOut {
  occurrences: Occurrence[]
  amount_history: AmountHistoryEntry[]
}

export interface StreamCreate {
  vendor_name: string
  product: string
  category: string
  cycle: Cycle
  expected_amount: number
  next_due?: string
  last_paid_date?: string
  auto_renew?: boolean
  paid_from?: string
  owner_name?: string
  pay_url?: string
  notes?: string
}

export interface StreamPatch {
  vendor_name?: string
  product?: string | null
  category?: string | null
  cycle?: Cycle
  expected_amount?: number | null
  next_due?: string | null
  status?: StreamStatus
  auto_renew?: boolean | null
  paid_from?: string | null
  owner_name?: string | null
  pay_url?: string | null
  reminder_on?: boolean
  notes?: string | null
}

export interface CategoryBreakdown {
  category: string | null
  monthly_equivalent: number
  count: number
}

export interface CalendarItem {
  stream_id: number
  vendor_name: string
  product: string | null
  amount: number
  due: string
}

export interface CalendarMonth {
  month: string // YYYY-MM
  cash_out: number
  items: CalendarItem[]
}

export interface SyncHealth {
  account_label: string
  source_kind: SourceKind
  last_data_date: string | null
  last_import_at: string | null
  stale: boolean
}

export interface Dashboard {
  month: string
  cash_out_month: number
  monthly_equivalent: number
  annualised: number
  active_count: number
  due_soon_count: number
  overdue_count: number
  needs_confirm_count: number
  by_category: CategoryBreakdown[]
  next_dues: StreamOut[]
  calendar: CalendarMonth[]
  committed_vs_manual: { auto_renew: number; manual: number }
  sync_health: SyncHealth[]
}

export interface QuestionOption {
  key: string
  label: string
}

export interface QuestionContext {
  payee?: string
  amount?: number
  dates?: string[]
  [key: string]: unknown
}

export interface Question {
  id: number
  kind: QuestionKind
  prompt: string
  context: QuestionContext
  options: QuestionOption[]
  stream_id?: number | null
  answered: boolean
  answer: unknown
  created_at: string
}

export interface AnswerResult {
  question: Question
  stream?: StreamOut | null
}

export interface UpcomingItem extends StreamOut {
  due: string
}

export interface UpcomingMonth {
  month: string
  total: number
  items: UpcomingItem[]
}

export interface Vendor {
  id: number
  key: string
  name: string
  category: string | null
  default_cycle: Cycle | null
  variable: boolean
  is_reseller: boolean
}

// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE = '/api'

export function getAccessKey(): string {
  try { return localStorage.getItem('it-tracker.accessKey') ?? '' } catch { return '' }
}
export function setAccessKey(k: string) {
  try { localStorage.setItem('it-tracker.accessKey', k) } catch { /* ignore */ }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    const headers = new Headers(init?.headers ?? {})
    const key = getAccessKey()
    if (key) headers.set('X-Access-Key', key)
    res = await fetch(BASE + path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the backend running on port 8000?')
  }
  if (res.status === 401) {
    const entered = window.prompt('This IT Tracker needs an access key. Enter it to continue:')
    if (entered) {
      setAccessKey(entered.trim())
      return request<T>(path, init)
    }
    throw new ApiError(401, 'Access key required.')
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body && typeof body.detail === 'string') msg = body.detail
      else if (Array.isArray(body?.detail)) {
        // FastAPI validation errors
        msg = body.detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            `${(d.loc ?? []).slice(-1)[0] ?? ''}: ${d.msg ?? ''}`.trim(),
          )
          .join('; ')
      }
    } catch {
      /* non-JSON body */
    }
    throw new ApiError(res.status, msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

// Companies
export const listCompanies = () => request<Company[]>('/companies')
export const createCompany = (body: { name: string; gstin?: string; fy_start_month?: number }) =>
  request<Company>('/companies', json('POST', body))
export const getCompany = (id: number) => request<Company>(`/companies/${id}`)

// Upload & engine
export function uploadFile(
  companyId: number,
  args: { file: File; source_kind: SourceKind; account_label: string; is_personal: boolean },
) {
  const fd = new FormData()
  fd.append('file', args.file)
  fd.append('source_kind', args.source_kind)
  fd.append('account_label', args.account_label)
  fd.append('is_personal', args.is_personal ? 'true' : 'false')
  return request<UploadResult>(`/companies/${companyId}/upload`, { method: 'POST', body: fd })
}
export const runEngine = (companyId: number) =>
  request<EngineSummary>(`/companies/${companyId}/run`, { method: 'POST' })
export const listImports = (companyId: number) =>
  request<ImportBatch[]>(`/companies/${companyId}/imports`)
export const listAccounts = (companyId: number) =>
  request<Account[]>(`/companies/${companyId}/accounts`)

// Dashboard
export const getDashboard = (companyId: number, month?: string) =>
  request<Dashboard>(`/companies/${companyId}/dashboard${qs({ month })}`)

// Streams
export const listStreams = (
  companyId: number,
  filters: { status?: string; category?: string; q?: string } = {},
) => request<StreamOut[]>(`/companies/${companyId}/streams${qs(filters)}`)
export const getStream = (companyId: number, sid: number) =>
  request<StreamDetail>(`/companies/${companyId}/streams/${sid}`)
export const createStream = (companyId: number, body: StreamCreate) =>
  request<StreamOut>(`/companies/${companyId}/streams`, json('POST', body))
export const patchStream = (companyId: number, sid: number, body: StreamPatch) =>
  request<StreamOut>(`/companies/${companyId}/streams/${sid}`, json('PATCH', body))
export const markPaid = (companyId: number, sid: number, body: { date: string; amount?: number }) =>
  request<StreamOut>(`/companies/${companyId}/streams/${sid}/mark-paid`, json('POST', body))
export const confirmStream = (companyId: number, sid: number, accept: boolean) =>
  request<StreamOut>(`/companies/${companyId}/streams/${sid}/confirm`, json('POST', { accept }))

// Questions
export const listQuestions = (companyId: number, open = true) =>
  request<Question[]>(`/companies/${companyId}/questions${qs({ open })}`)
export const answerQuestion = (
  companyId: number,
  qid: number,
  body: { choice: string; text?: string },
) => request<AnswerResult>(`/companies/${companyId}/questions/${qid}/answer`, json('POST', body))

// Upcoming
export const getUpcoming = (companyId: number, days = 90) =>
  request<UpcomingMonth[]>(`/companies/${companyId}/upcoming${qs({ days })}`)

// Vendors
export const listVendors = (q?: string) => request<Vendor[]>(`/vendors${qs({ q })}`)
