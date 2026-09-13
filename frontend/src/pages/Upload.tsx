import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createCompany,
  listAccounts,
  listImports,
  runEngine,
  uploadFile,
  type Company,
  type EngineSummary,
  type ImportBatch,
  type SourceKind,
  type UploadResult,
} from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText, type FetchState } from '../lib/useFetch'
import { notifyDataChanged, useDataChanged } from '../lib/events'
import { fmtDateTime } from '../lib/format'
import { Empty, ErrorMsg, Loading } from '../components/ui'

const SOURCE_KINDS: { value: SourceKind; label: string }[] = [
  { value: 'bank', label: 'Bank statement' },
  { value: 'card', label: 'Card statement' },
  { value: 'tally', label: 'Tally purchase register' },
  { value: 'generic', label: 'Other Excel / CSV' },
]

const LS_LABEL = 'it-tracker.last_account_label'

/** Sensible account label when the user hasn't typed one. */
const DEFAULT_LABEL: Partial<Record<SourceKind, string>> = {
  tally: 'Tally purchase register',
  card: 'Company card',
}

export default function Upload() {
  const { companyId, companies, select, add, canEdit } = useCompany()
  const imports = useFetch(() => listImports(companyId as number), [companyId], companyId !== null)
  useDataChanged(imports.reload)
  const firstTime = !!imports.data && imports.data.length === 0

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Upload</h1>
          <p>Bank, card or Tally exports. We check for licences and subscriptions right after each upload.</p>
        </div>
      </div>

      {companyId !== null && canEdit && <Onboarding open={firstTime} />}

      {companyId === null ? (
        <div className="card">
          <Empty title="Create a company first">Every upload belongs to a company.</Empty>
        </div>
      ) : !canEdit ? (
        <div className="msg msg-muted">You have view-only access to this company, so you cannot upload statements.</div>
      ) : (
        <UploadForm
          key={companyId}
          companyId={companyId}
          companies={companies.map((c) => ({ id: c.id, name: c.name }))}
          onSelectCompany={select}
        />
      )}

      {companyId !== null && (
        <ImportsList key={`imports-${companyId}`} companyId={companyId} imports={imports} canEdit={canEdit} />
      )}

      <CreateCompany onCreated={add} />
    </div>
  )
}

const BANK_STEPS: { bank: string; steps: string[] }[] = [
  {
    bank: 'HDFC Bank',
    steps: [
      'Log in to HDFC NetBanking → Accounts → Account Statement.',
      'Pick the account, choose "Select period" and set the from/to dates (up to 24 months back).',
      'Under "View / Download" choose "Excel" (or "Delimited" for CSV) and download.',
    ],
  },
  {
    bank: 'ICICI Bank',
    steps: [
      'Log in to ICICI internet banking → Bank Accounts → Statements → Detailed statement.',
      'Choose "Select date range" and enter the period.',
      'Choose "Excel" as the format and click Download.',
    ],
  },
  {
    bank: 'SBI',
    steps: [
      'Log in to OnlineSBI → My Accounts & Profile → Account Statement.',
      'Pick the account and the date range (do it in 6-month chunks if SBI limits you).',
      'Choose "Download in MS Excel format" and press Go.',
    ],
  },
  {
    bank: 'Axis Bank',
    steps: [
      'Log in to Axis internet banking → Accounts → Statement (Detailed).',
      'Select the date range.',
      'Choose "Excel" under Download and save the file.',
    ],
  },
  {
    bank: 'Kotak',
    steps: [
      'Log in to Kotak net banking → Banking → Account Statement.',
      'Choose the account and "Custom period", set the dates.',
      'Choose "Excel" or "CSV" as the download format.',
    ],
  },
]

function Onboarding({ open: defaultOpen }: { open: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const [bank, setBank] = useState<string | null>(null)
  // First upload finished → collapse the help so it stops taking space.
  useEffect(() => setOpen(defaultOpen), [defaultOpen])

  return (
    <div className="card onboarding">
      <div className="row">
        <h2>{defaultOpen ? 'Getting started — three steps' : 'How to get your statements'}</h2>
        <span className="spacer" />
        <button type="button" className="btn btn-sm" onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide' : 'Show'}
        </button>
      </div>
      {open && (
        <ol className="steps">
          <li>
            <strong>Download 12–24 months from net banking as Excel.</strong>
            <div className="muted small" style={{ margin: '4px 0 6px' }}>
              Longer is better — yearly licences only show up once a year. Pick your bank for the exact clicks:
            </div>
            <div className="row">
              {BANK_STEPS.map((b) => (
                <button
                  key={b.bank}
                  type="button"
                  className={`btn btn-sm${bank === b.bank ? ' btn-primary' : ''}`}
                  onClick={() => setBank(bank === b.bank ? null : b.bank)}
                >
                  {b.bank}
                </button>
              ))}
            </div>
            {bank && (
              <ol className="bank-steps">
                {BANK_STEPS.find((b) => b.bank === bank)!.steps.map((st) => (
                  <li key={st}>{st}</li>
                ))}
              </ol>
            )}
            <div className="muted small" style={{ marginTop: 6 }}>
              PDF statements also work. If the PDF asks for a password, enter it below when you upload.
            </div>
          </li>
          <li>
            <strong>Optional: Tally purchase register.</strong>
            <div className="muted small" style={{ marginTop: 4 }}>
              In Tally: Display → Account Books → Purchase Register → set the period → press <kbd>Ctrl+E</kbd> → choose
              Excel. This adds invoices that were booked but paid from another account.
            </div>
          </li>
          <li>
            <strong>Upload here.</strong>
            <div className="muted small" style={{ marginTop: 4 }}>
              One file at a time. Uploading the same statement twice is safe — we skip what we already have.
            </div>
          </li>
        </ol>
      )}
    </div>
  )
}

function UploadForm({
  companyId,
  companies,
  onSelectCompany,
}: {
  companyId: number
  companies: { id: number; name: string }[]
  onSelectCompany: (id: number) => void
}) {
  const [sourceKind, setSourceKind] = useState<SourceKind>('bank')
  const [label, setLabel] = useState(() => {
    try {
      return localStorage.getItem(LS_LABEL) ?? ''
    } catch {
      return ''
    }
  })
  const [labelTouched, setLabelTouched] = useState(false)
  const [personal, setPersonal] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [pdfPassword, setPdfPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const isPdf = !!file && /\.pdf$/i.test(file.name)

  const accounts = useFetch(() => listAccounts(companyId), [companyId])

  function changeSource(k: SourceKind) {
    setSourceKind(k)
    // Fill the label from the source kind unless the user typed their own
    // (a bank label they typed comes back when they switch back to bank).
    if (!labelTouched) {
      let stored = ''
      try {
        stored = localStorage.getItem(LS_LABEL) ?? ''
      } catch {
        /* ignore */
      }
      setLabel(DEFAULT_LABEL[k] ?? stored)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!file) return setErr('Choose a file to upload.')
    if (!label.trim()) return setErr('Give the account a label, e.g. "HDFC Current".')
    setBusy(true)
    try {
      const r = await uploadFile(companyId, {
        file,
        source_kind: sourceKind,
        account_label: label.trim(),
        is_personal: personal,
        pdf_password: isPdf && pdfPassword ? pdfPassword : undefined,
      })
      setResult(r)
      try {
        localStorage.setItem(LS_LABEL, label.trim())
      } catch {
        /* ignore */
      }
      setFile(null)
      setPdfPassword('')
      setFileKey((k) => k + 1)
      // The next file is probably a different source (bank → Tally): let the
      // label follow the source again instead of carrying "HDFC Current" over.
      setLabelTouched(false)
      accounts.reload()
      notifyDataChanged()
    } catch (e2) {
      setResult(null) // don't leave the previous file's success box under the error
      setErr(errorText(e2))
      notifyDataChanged() // the failed batch is recorded; show it in Previous imports
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 style={{ marginBottom: 12 }}>Upload a statement</h2>
      <div className="form-row">
        <label className="field">
          <span>Company</span>
          <select value={companyId} onChange={(e) => onSelectCompany(parseInt(e.target.value, 10))}>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Source</span>
          <select value={sourceKind} onChange={(e) => changeSource(e.target.value as SourceKind)}>
            {SOURCE_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Account label</span>
          <input
            type="text"
            list="account-labels"
            value={label}
            onChange={(e) => {
              setLabel(e.target.value)
              setLabelTouched(true)
            }}
            placeholder='e.g. "HDFC Current", "MD personal card"'
            required
          />
          <datalist id="account-labels">
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.label} />
            ))}
          </datalist>
        </label>
        <label className="field">
          <span>File (xlsx, xls, csv, pdf)</span>
          <input
            key={fileKey}
            type="file"
            accept=".xlsx,.xls,.csv,.pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv,application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        {isPdf && (
          <label className="field">
            <span>PDF password (if the statement is locked)</span>
            <input
              type="password"
              value={pdfPassword}
              onChange={(e) => setPdfPassword(e.target.value)}
              autoComplete="off"
              placeholder="Leave blank if it opens without one"
            />
            <div className="muted small" style={{ marginTop: 4 }}>
              Banks usually use your customer ID, PAN, or date of birth (e.g. DDMMYYYY). We use it only to open this
              file and do not store it.
            </div>
          </label>
        )}
      </div>
      <label className="check">
        <input type="checkbox" checked={personal} onChange={(e) => setPersonal(e.target.checked)} />
        This is a personal account (owner's own card or bank) used for company software
      </label>
      {err && (
        <div style={{ marginBottom: 10 }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Uploading and checking…' : 'Upload'}
        </button>
        {busy && <span className="muted small">Large files can take a minute.</span>}
      </div>

      {result && (
        <div style={{ marginTop: 16 }}>
          {result.batch.rows_imported === 0 && !result.batch.error ? (
            <div className="msg msg-warn">
              <strong>{result.batch.filename}</strong> — {result.hint || 'This statement was already uploaded'}.
              {result.batch.rows_skipped ? ` ${result.batch.rows_skipped} rows were already on file.` : ''}
            </div>
          ) : (
            <div className={`msg ${result.batch.error ? 'msg-warn' : 'msg-ok'}`}>
              <strong>{result.batch.filename}</strong> — {result.batch.rows_imported} rows imported
              {result.batch.rows_skipped ? `, ${result.batch.rows_skipped} skipped (already on file)` : ''}
              {result.detected_bank ? ` · looks like ${result.detected_bank}` : ''}
              {!result.detected_bank && result.batch.detected_format ? ` · format: ${result.batch.detected_format}` : ''}
              {result.batch.error ? <div style={{ marginTop: 4 }}>{result.batch.error}</div> : null}
              {result.hint && result.batch.rows_imported > 0 ? <div style={{ marginTop: 4 }}>{result.hint}</div> : null}
            </div>
          )}
          <EngineBox engine={result.engine} />
        </div>
      )}
    </form>
  )
}

function EngineBox({ engine }: { engine: EngineSummary }) {
  // "Needs confirm" lines and open questions overlap; one number, one button.
  const toAnswer = Math.max(engine.questions_open, engine.needs_confirm)
  return (
    <div className="card" style={{ marginTop: 10, background: 'var(--surface-2)', boxShadow: 'none' }}>
      <div className="card-title">What we found</div>
      <div className="grid-4">
        <Stat label="Payments" value={engine.occurrences} />
        <Stat label="Licences & subscriptions" value={engine.streams} />
        <Stat label="Recognised" value={engine.auto_accepted} />
        <Stat label="Not recognised" value={engine.unclassified} />
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        {toAnswer > 0 ? (
          <Link to={engine.questions_open > 0 ? '/attention' : '/lines?status=needs_confirm'} className="btn btn-sm btn-primary">
            {toAnswer} payment{toAnswer === 1 ? ' needs' : 's need'} a quick answer →
          </Link>
        ) : (
          <span className="small" style={{ color: 'var(--ok)' }}>Nothing to check — all clear.</span>
        )}
        <span className="spacer" />
        <span className="muted small">Checked {fmtDateTime(engine.ran_at)}</span>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="counter-value num">{value.toLocaleString('en-IN')}</div>
      <div className="counter-label">{label}</div>
    </div>
  )
}

function ImportsList({
  companyId,
  imports,
  canEdit,
}: {
  companyId: number
  imports: FetchState<ImportBatch[]>
  canEdit: boolean
}) {
  const [running, setRunning] = useState(false)
  const [runErr, setRunErr] = useState<string | null>(null)
  const [runResult, setRunResult] = useState<EngineSummary | null>(null)

  async function rerun() {
    setRunning(true)
    setRunErr(null)
    setRunResult(null)
    try {
      const r = await runEngine(companyId)
      setRunResult(r)
      notifyDataChanged()
    } catch (e) {
      setRunErr(errorText(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="card">
      <div className="row" style={{ marginBottom: 10 }}>
        <h2>Previous imports</h2>
        <span className="spacer" />
        <button className="btn btn-sm" onClick={imports.reload} disabled={imports.loading}>
          Refresh
        </button>
        {canEdit && (
          <button className="btn btn-sm" onClick={rerun} disabled={running} title="Check all statements again">
            {running ? 'Checking…' : 'Re-check'}
          </button>
        )}
      </div>
      {runErr && (
        <div style={{ marginBottom: 10 }}>
          <ErrorMsg>{runErr}</ErrorMsg>
        </div>
      )}
      {runResult && <EngineBox engine={runResult} />}
      {imports.loading && !imports.data ? (
        <Loading />
      ) : imports.error ? (
        <ErrorMsg>{imports.error}</ErrorMsg>
      ) : !imports.data || imports.data.length === 0 ? (
        <Empty title="No imports yet" />
      ) : (
        <div className="table-wrap" style={{ marginTop: 10 }}>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>File</th>
                <th>Source</th>
                <th>Account</th>
                <th className="right">Imported</th>
                <th className="right">Skipped</th>
                <th>Format</th>
              </tr>
            </thead>
            <tbody>
              {imports.data.map((b) => (
                <tr key={b.id}>
                  <td>{fmtDateTime(b.created_at)}</td>
                  <td>
                    {b.filename}
                    {b.error ? <div className="cell-sub" style={{ color: 'var(--danger)' }}>{b.error}</div> : null}
                  </td>
                  <td>{SOURCE_KINDS.find((k) => k.value === b.source_kind)?.label ?? b.source_kind}</td>
                  <td>{b.account_label}</td>
                  <td className="right num">{b.rows_imported}</td>
                  <td className="right num">{b.rows_skipped}</td>
                  <td className="muted">{b.detected_format ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CreateCompany({ onCreated }: { onCreated: (c: Company) => void }) {
  const [name, setName] = useState('')
  const [gstin, setGstin] = useState('')
  const [fy, setFy] = useState(4)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return setErr('Company name is required.')
    setBusy(true)
    setErr(null)
    try {
      const body: { name: string; gstin?: string; fy_start_month?: number } = {
        name: name.trim(),
        fy_start_month: fy,
      }
      if (gstin.trim()) body.gstin = gstin.trim().toUpperCase()
      const c = await createCompany(body)
      onCreated(c)
      setName('')
      setGstin('')
      setOpen(false)
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div className="card">
        <div className="row">
          <div>
            <h2>Create company</h2>
            <div className="muted small">Add another factory or entity to track separately.</div>
          </div>
          <span className="spacer" />
          <button className="btn" onClick={() => setOpen(true)}>
            New company
          </button>
        </div>
      </div>
    )
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 style={{ marginBottom: 12 }}>Create company</h2>
      <div className="form-row">
        <label className="field">
          <span>Name *</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        </label>
        <label className="field">
          <span>GSTIN (optional)</span>
          <input
            type="text"
            value={gstin}
            onChange={(e) => setGstin(e.target.value)}
            placeholder="15 characters"
            maxLength={15}
          />
        </label>
        <label className="field">
          <span>Financial year starts in</span>
          <select value={fy} onChange={(e) => setFy(parseInt(e.target.value, 10))}>
            {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map(
              (m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ),
            )}
          </select>
        </label>
      </div>
      {err && (
        <div style={{ marginBottom: 10 }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Creating…' : 'Create'}
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  )
}
