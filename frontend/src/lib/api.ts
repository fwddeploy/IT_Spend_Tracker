// Typed client for the IT Tracker API (docs/API.md v1 + docs/API-v2-additions.md).
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
  /** Not in the v1 contract; the settings route is the source of truth. */
  short_name?: string | null
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
  /** v2: e.g. "HDFC", "ICICI" when recognisable from the header rows. */
  detected_bank?: string | null
  /** v2: set when 0 rows were imported ("This statement was already uploaded"). */
  hint?: string | null
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
  // v2 additions (optional so the UI also works against a v1 backend)
  /** 18% of expected for foreign no-GST vendors (reverse charge), else null. */
  rcm_gst?: number | null
  quantity?: number | null
  unit_price?: number | null
  /** FY of the last occurrence's service period, e.g. "2026-27". */
  fy?: string | null
  /** Plain-English versions of `flags`. */
  flags_human?: string[]
  /** Payees seen over time when the supplier changed. */
  supplier_history?: string[]
  /** Set by the backend when it changed something the user should know about. */
  change_note?: string | null
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

export interface CashBreakdown {
  paid: number
  still_due: number
  estimate: number
}

export interface Dashboard {
  month: string
  cash_out_month: number
  cash_breakdown?: CashBreakdown | null
  /** FY view (`?fy=`): "FY 2026-27" and the Apr–Mar total. */
  period?: string | null
  cash_out_period?: number | null
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

/** One row of a "Split into several" answer for a `bundle` question. */
export interface SplitItem {
  vendor_key: string
  product: string
  amount: number
}

export interface AnswerBody {
  choice: string
  text?: string
  items?: SplitItem[]
}

export interface BulkAnswer {
  question_id: number
  choice: string
  text?: string
}

export interface BulkAnswerResult {
  answered: number
  engine: EngineSummary
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

// ---- v2: auth, settings, aliases, reminders, share, audit ------------------

export type Role = 'owner' | 'accountant' | 'viewer'
export const ROLES: Role[] = ['owner', 'accountant', 'viewer']

export interface User {
  id: number
  name: string
  email: string
}

export interface AuthCompany {
  id: number
  name: string
  role: Role
}

export interface AuthResult {
  user: User
  companies: AuthCompany[]
}

export interface InviteResult {
  email: string
  temp_password: string
  role: Role
}

export type DigestDay = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'

export interface ReminderDays {
  monthly: number
  quarterly: number
  yearly: number
}

export interface CompanySettings {
  name: string
  gstin: string | null
  fy_start_month: number
  owner_phone: string | null
  owner_email: string | null
  accountant_email: string | null
  whatsapp_enabled: boolean
  email_enabled: boolean
  reminder_days_before: ReminderDays
  weekly_digest_day: DigestDay | null
  short_name: string | null
}

export type CompanySettingsPatch = Partial<CompanySettings>

export interface Alias {
  id: number
  /** Display text of the payee this rule applies to. */
  pattern: string
  vendor_name: string | null
  product: string | null
  created_at: string
  hidden: boolean
}

export type ReminderChannel = 'whatsapp' | 'email'

export interface ReminderPreview {
  stream_id: number
  vendor_name: string
  product: string | null
  amount: number
  due: string
  days_before: number
  channel: ReminderChannel[]
  will_send_on: string
}

export interface ReminderSendResult {
  sent: { channel: ReminderChannel; to: string; ok: boolean; error?: string | null }[]
}

export interface ReminderLogEntry {
  id: number
  stream_id: number
  vendor_name: string
  channel: ReminderChannel
  to: string
  sent_at: string
  status: string // "sent" | "failed" | "skipped_not_configured" | ...
  message: string
}

export interface ShareText {
  text: string
}

export interface AuditEvent {
  id: number
  at: string
  user: string
  action: string
  target: string
  detail: string
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

/** Fired when any non-auth request comes back 401 so the app can go to /login. */
export const UNAUTHORIZED_EVENT = 'it-tracker:unauthorized'

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
    res = await fetch(BASE + path, { ...init, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the backend running on port 8000?')
  }
  if (res.status === 401) {
    let detail = ''
    try {
      const body = await res.clone().json()
      if (body && typeof body.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON body */
    }
    // Legacy gate: the server still runs with APP_ACCESS_KEY only. Ask once.
    if (/access key required/i.test(detail)) {
      const entered = window.prompt('This IT Tracker needs an access key. Enter it to continue:')
      if (entered) {
        setAccessKey(entered.trim())
        return request<T>(path, init)
      }
      throw new ApiError(401, 'Access key required.')
    }
    // Normal case: not logged in (or session expired) → the auth provider sends the user to /login.
    if (!path.startsWith('/auth/')) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new ApiError(401, detail || 'Please log in.')
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
  args: {
    file: File
    source_kind: SourceKind
    account_label: string
    is_personal: boolean
    pdf_password?: string
  },
) {
  const fd = new FormData()
  fd.append('file', args.file)
  fd.append('source_kind', args.source_kind)
  fd.append('account_label', args.account_label)
  fd.append('is_personal', args.is_personal ? 'true' : 'false')
  if (args.pdf_password) fd.append('pdf_password', args.pdf_password)
  return request<UploadResult>(`/companies/${companyId}/upload`, { method: 'POST', body: fd })
}
export const runEngine = (companyId: number) =>
  request<EngineSummary>(`/companies/${companyId}/run`, { method: 'POST' })
export const listImports = (companyId: number) =>
  request<ImportBatch[]>(`/companies/${companyId}/imports`)
export const listAccounts = (companyId: number) =>
  request<Account[]>(`/companies/${companyId}/accounts`)

// Dashboard
export const getDashboard = (companyId: number, opts: { month?: string; fy?: number | string } = {}) =>
  request<Dashboard>(`/companies/${companyId}/dashboard${qs(opts)}`)

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
export const answerQuestion = (companyId: number, qid: number, body: AnswerBody) =>
  request<AnswerResult>(`/companies/${companyId}/questions/${qid}/answer`, json('POST', body))
export const answerBulk = (companyId: number, answers: BulkAnswer[]) =>
  request<BulkAnswerResult>(`/companies/${companyId}/questions/answer-bulk`, json('POST', { answers }))

// Upcoming
export const getUpcoming = (companyId: number, days = 90) =>
  request<UpcomingMonth[]>(`/companies/${companyId}/upcoming${qs({ days })}`)

// Vendors
export const listVendors = (q?: string) => request<Vendor[]>(`/vendors${qs({ q })}`)

// ---- v2 routes -------------------------------------------------------------

// Auth (cookie session)
export const register = (body: { name: string; email: string; password: string; company_name: string }) =>
  request<AuthResult>('/auth/register', json('POST', body))
export const login = (body: { email: string; password: string }) =>
  request<AuthResult>('/auth/login', json('POST', body))
export const logout = () => request<void>('/auth/logout', { method: 'POST' })
export const getMe = () => request<AuthResult>('/auth/me')
export const inviteUser = (body: { company_id: number; email: string; role: Role }) =>
  request<InviteResult>('/auth/invite', json('POST', body))

// Company settings
export const getSettings = (companyId: number) =>
  request<CompanySettings>(`/companies/${companyId}/settings`)
export const patchSettings = (companyId: number, body: CompanySettingsPatch) =>
  request<CompanySettings>(`/companies/${companyId}/settings`, json('PATCH', body))
export const deleteCompany = (companyId: number) =>
  request<void>(`/companies/${companyId}`, { method: 'DELETE' })

// Hidden payees / learned answers
export const listAliases = (companyId: number) => request<Alias[]>(`/companies/${companyId}/aliases`)
export const deleteAlias = (companyId: number, aliasId: number) =>
  request<void>(`/companies/${companyId}/aliases/${aliasId}`, { method: 'DELETE' })

// Reminders
export const getReminderPreview = (companyId: number, days = 30) =>
  request<ReminderPreview[]>(`/companies/${companyId}/reminders${qs({ days })}`)
export const sendReminderNow = (companyId: number, streamId: number) =>
  request<ReminderSendResult>(`/companies/${companyId}/reminders/send-now`, json('POST', { stream_id: streamId }))
export const getReminderLog = (companyId: number, limit = 50) =>
  request<ReminderLogEntry[]>(`/companies/${companyId}/reminders/log${qs({ limit })}`)

// Owner share + export
export const getShareText = (companyId: number) => request<ShareText>(`/companies/${companyId}/share-text`)
export const exportUrl = (companyId: number) => `${BASE}/companies/${companyId}/export.xlsx`

// Audit
export const listEvents = (companyId: number, limit = 100) =>
  request<AuditEvent[]>(`/companies/${companyId}/events${qs({ limit })}`)
