import { useState } from 'react'
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
} from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged } from '../lib/events'
import { fmtDateTime } from '../lib/format'
import { Empty, ErrorMsg, Loading } from '../components/ui'

const SOURCE_KINDS: { value: SourceKind; label: string }[] = [
  { value: 'bank', label: 'Bank statement' },
  { value: 'card', label: 'Card statement' },
  { value: 'tally', label: 'Tally purchase register' },
  { value: 'generic', label: 'Other Excel / CSV' },
]

const LS_LABEL = 'it-tracker.last_account_label'

export default function Upload() {
  const { companyId, companies, select, add } = useCompany()

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Upload</h1>
          <p>Bank, card or Tally exports. The engine runs automatically after each upload.</p>
        </div>
      </div>

      {companyId === null ? (
        <div className="card">
          <Empty title="Create a company first">Every upload belongs to a company.</Empty>
        </div>
      ) : (
        <UploadForm
          key={companyId}
          companyId={companyId}
          companies={companies.map((c) => ({ id: c.id, name: c.name }))}
          onSelectCompany={select}
        />
      )}

      {companyId !== null && <ImportsList key={`imports-${companyId}`} companyId={companyId} />}

      <CreateCompany onCreated={add} />
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
  const [personal, setPersonal] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<{ batch: ImportBatch; engine: EngineSummary } | null>(null)
  const [fileKey, setFileKey] = useState(0)

  const accounts = useFetch(() => listAccounts(companyId), [companyId])

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
      })
      setResult(r)
      try {
        localStorage.setItem(LS_LABEL, label.trim())
      } catch {
        /* ignore */
      }
      setFile(null)
      setFileKey((k) => k + 1)
      accounts.reload()
      notifyDataChanged()
    } catch (e2) {
      setErr(errorText(e2))
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
          <select value={sourceKind} onChange={(e) => setSourceKind(e.target.value as SourceKind)}>
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
            onChange={(e) => setLabel(e.target.value)}
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
          {busy ? 'Uploading and running engine…' : 'Upload'}
        </button>
        {busy && <span className="muted small">Large files can take a minute.</span>}
      </div>

      {result && (
        <div style={{ marginTop: 16 }}>
          <div className={`msg ${result.batch.error ? 'msg-warn' : 'msg-ok'}`}>
            <strong>{result.batch.filename}</strong> — {result.batch.rows_imported} rows imported
            {result.batch.rows_skipped ? `, ${result.batch.rows_skipped} skipped` : ''}
            {result.batch.detected_format ? ` · detected format: ${result.batch.detected_format}` : ''}
            {result.batch.error ? <div style={{ marginTop: 4 }}>{result.batch.error}</div> : null}
          </div>
          <EngineBox engine={result.engine} />
        </div>
      )}
    </form>
  )
}

function EngineBox({ engine }: { engine: EngineSummary }) {
  return (
    <div className="card" style={{ marginTop: 10, background: 'var(--surface-2)', boxShadow: 'none' }}>
      <div className="card-title">Engine summary</div>
      <div className="grid-4">
        <Stat label="Payments matched" value={engine.occurrences} />
        <Stat label="Lines" value={engine.streams} />
        <Stat label="Auto-accepted" value={engine.auto_accepted} />
        <Stat label="Unclassified" value={engine.unclassified} />
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        {engine.needs_confirm > 0 && (
          <Link to="/lines?status=needs_confirm" className="btn btn-sm">
            {engine.needs_confirm} need confirm
          </Link>
        )}
        {engine.questions_open > 0 && (
          <Link to="/attention" className="btn btn-sm btn-primary">
            Answer {engine.questions_open} question{engine.questions_open === 1 ? '' : 's'}
          </Link>
        )}
        <span className="spacer" />
        <span className="muted small">Ran {fmtDateTime(engine.ran_at)}</span>
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

function ImportsList({ companyId }: { companyId: number }) {
  const imports = useFetch(() => listImports(companyId), [companyId])
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
        <button className="btn btn-sm" onClick={rerun} disabled={running}>
          {running ? 'Running…' : 'Re-run engine'}
        </button>
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
