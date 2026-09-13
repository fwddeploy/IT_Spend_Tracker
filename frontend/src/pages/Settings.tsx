import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ROLES,
  deleteAlias,
  deleteCompany,
  getReminderLog,
  getReminderPreview,
  getSettings,
  inviteUser,
  listAliases,
  patchSettings,
  sendReminderNow,
  type CompanySettings,
  type CompanySettingsPatch,
  type DigestDay,
  type InviteResult,
  type ReminderSendResult,
  type Role,
} from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged, useDataChanged } from '../lib/events'
import { fmtDate, fmtDateTime, rupees, dayLabel, humanize } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany } from '../components/ui'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const DIGEST_DAYS: DigestDay[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
const ROLE_HELP: Record<Role, string> = {
  owner: 'Everything, including settings and deleting the company',
  accountant: 'Can upload, edit licences and answer questions',
  viewer: 'Can only look',
}

interface Form {
  name: string
  short_name: string
  gstin: string
  fy_start_month: number
  owner_phone: string
  owner_email: string
  accountant_email: string
  whatsapp_enabled: boolean
  email_enabled: boolean
  monthly: string
  quarterly: string
  yearly: string
  weekly_digest_day: string
}

function toForm(s: CompanySettings): Form {
  return {
    name: s.name ?? '',
    short_name: s.short_name ?? '',
    gstin: s.gstin ?? '',
    fy_start_month: s.fy_start_month ?? 4,
    owner_phone: s.owner_phone ?? '',
    owner_email: s.owner_email ?? '',
    accountant_email: s.accountant_email ?? '',
    whatsapp_enabled: !!s.whatsapp_enabled,
    email_enabled: !!s.email_enabled,
    monthly: String(s.reminder_days_before?.monthly ?? 5),
    quarterly: String(s.reminder_days_before?.quarterly ?? 10),
    yearly: String(s.reminder_days_before?.yearly ?? 30),
    weekly_digest_day: s.weekly_digest_day ?? '',
  }
}

export default function Settings() {
  const { companyId, company, canEdit, isOwner, reload: reloadCompanies } = useCompany()
  if (companyId === null) return <NoCompany />
  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>{company?.name}</p>
        </div>
      </div>
      {!canEdit && (
        <div className="msg msg-muted">You have view-only access to this company. Settings cannot be changed.</div>
      )}
      <SettingsForm key={`s-${companyId}`} companyId={companyId} canEdit={canEdit} onSaved={reloadCompanies} />
      <Reminders key={`r-${companyId}`} companyId={companyId} canEdit={canEdit} />
      <Aliases key={`a-${companyId}`} companyId={companyId} canEdit={canEdit} />
      {isOwner && <Invite key={`i-${companyId}`} companyId={companyId} />}
      {isOwner && <DeleteCompany key={`d-${companyId}`} companyId={companyId} companyName={company?.name ?? ''} />}
    </div>
  )
}

function SettingsForm({
  companyId,
  canEdit,
  onSaved,
}: {
  companyId: number
  canEdit: boolean
  onSaved: () => Promise<void>
}) {
  const settings = useFetch(() => getSettings(companyId), [companyId])
  const [form, setForm] = useState<Form | null>(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  useEffect(() => {
    if (settings.data) setForm(toForm(settings.data))
  }, [settings.data])

  const s = settings.data
  const dirty = s && form ? JSON.stringify(form) !== JSON.stringify(toForm(s)) : false

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!form || !s) return
    setErr(null)
    setOk(false)
    if (!form.name.trim()) return setErr('Company name is required.')
    const phone = form.owner_phone.trim()
    if (phone && !/^\+?[0-9 ]{10,15}$/.test(phone)) return setErr('Owner phone should be like +91 98765 43210.')
    const days = {
      monthly: parseInt(form.monthly, 10),
      quarterly: parseInt(form.quarterly, 10),
      yearly: parseInt(form.yearly, 10),
    }
    if (Object.values(days).some((n) => Number.isNaN(n) || n < 0 || n > 365))
      return setErr('Reminder days must be whole numbers between 0 and 365.')
    const body: CompanySettingsPatch = {
      name: form.name.trim(),
      short_name: form.short_name.trim() || null,
      gstin: form.gstin.trim().toUpperCase() || null,
      fy_start_month: form.fy_start_month,
      owner_phone: phone ? (phone.startsWith('+') ? phone : '+91 ' + phone) : null,
      owner_email: form.owner_email.trim() || null,
      accountant_email: form.accountant_email.trim() || null,
      whatsapp_enabled: form.whatsapp_enabled,
      email_enabled: form.email_enabled,
      reminder_days_before: days,
      weekly_digest_day: (form.weekly_digest_day || null) as DigestDay | null,
    }
    setSaving(true)
    try {
      const updated = await patchSettings(companyId, body)
      settings.setData(updated)
      setOk(true)
      notifyDataChanged() // top bar short name, reminder preview
      await onSaved()
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setSaving(false)
    }
  }

  if (settings.loading && !s) return <div className="card"><Loading text="Loading settings…" /></div>
  if (settings.error) return <div className="card"><ErrorMsg>{settings.error}</ErrorMsg></div>
  if (!form) return null

  return (
    <form className="card" onSubmit={save}>
      <fieldset disabled={!canEdit} style={{ border: 'none', padding: 0, margin: 0, minWidth: 0 }}>
        <h2 style={{ marginBottom: 12 }}>Company details</h2>
        <div className="form-row">
          <label className="field">
            <span>Company name</span>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </label>
          <label className="field">
            <span>Short name (shown in the top bar and in reminders)</span>
            <input
              type="text"
              value={form.short_name}
              onChange={(e) => setForm({ ...form, short_name: e.target.value })}
              placeholder="e.g. Sharma Auto"
              maxLength={40}
            />
          </label>
          <label className="field">
            <span>GSTIN</span>
            <input
              type="text"
              value={form.gstin}
              onChange={(e) => setForm({ ...form, gstin: e.target.value })}
              placeholder="15 characters"
              maxLength={15}
            />
          </label>
          <label className="field">
            <span>Financial year starts in</span>
            <select
              value={form.fy_start_month}
              onChange={(e) => setForm({ ...form, fy_start_month: parseInt(e.target.value, 10) })}
            >
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </div>

        <h2 style={{ margin: '14px 0 4px' }}>Reminders</h2>
        <p className="muted small" style={{ margin: '0 0 12px' }}>
          Before a payment is due we send a short message on WhatsApp and/or email. Turn on the channels you want.
        </p>
        <div className="form-row">
          <label className="field">
            <span>Owner phone (WhatsApp, +91)</span>
            <input
              type="text"
              inputMode="tel"
              value={form.owner_phone}
              onChange={(e) => setForm({ ...form, owner_phone: e.target.value })}
              placeholder="+91 98765 43210"
            />
          </label>
          <label className="field">
            <span>Owner email</span>
            <input
              type="email"
              value={form.owner_email}
              onChange={(e) => setForm({ ...form, owner_email: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Accountant email</span>
            <input
              type="email"
              value={form.accountant_email}
              onChange={(e) => setForm({ ...form, accountant_email: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Weekly summary</span>
            <select
              value={form.weekly_digest_day}
              onChange={(e) => setForm({ ...form, weekly_digest_day: e.target.value })}
            >
              <option value="">Off</option>
              {DIGEST_DAYS.map((d) => (
                <option key={d} value={d}>
                  Every {dayLabel(d)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={form.whatsapp_enabled}
            onChange={(e) => setForm({ ...form, whatsapp_enabled: e.target.checked })}
          />
          Send reminders on WhatsApp
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.email_enabled}
            onChange={(e) => setForm({ ...form, email_enabled: e.target.checked })}
          />
          Send reminders by email
        </label>
        <div className="muted small" style={{ margin: '8px 0 4px' }}>How many days before the due date to remind:</div>
        <div className="row">
          <label className="field field-inline">
            <span>Monthly payments</span>
            <input
              type="number"
              min={0}
              max={365}
              value={form.monthly}
              onChange={(e) => setForm({ ...form, monthly: e.target.value })}
            />
          </label>
          <label className="field field-inline">
            <span>Quarterly</span>
            <input
              type="number"
              min={0}
              max={365}
              value={form.quarterly}
              onChange={(e) => setForm({ ...form, quarterly: e.target.value })}
            />
          </label>
          <label className="field field-inline">
            <span>Yearly and longer</span>
            <input
              type="number"
              min={0}
              max={365}
              value={form.yearly}
              onChange={(e) => setForm({ ...form, yearly: e.target.value })}
            />
          </label>
        </div>
        {err && (
          <div style={{ margin: '10px 0' }}>
            <ErrorMsg>{err}</ErrorMsg>
          </div>
        )}
        {canEdit && (
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={saving || !dirty}>
              {saving ? 'Saving…' : 'Save settings'}
            </button>
            {dirty && (
              <button type="button" className="btn" disabled={saving} onClick={() => setForm(toForm(s!))}>
                Discard
              </button>
            )}
            {ok && !dirty && <span className="small" style={{ color: 'var(--ok)' }}>Saved.</span>}
          </div>
        )}
      </fieldset>
    </form>
  )
}

function Reminders({ companyId, canEdit }: { companyId: number; canEdit: boolean }) {
  const preview = useFetch(() => getReminderPreview(companyId, 30), [companyId])
  const log = useFetch(() => getReminderLog(companyId, 50), [companyId])
  useDataChanged(preview.reload)
  const [sending, setSending] = useState<number | null>(null)
  const [sendResult, setSendResult] = useState<{ streamId: number; r?: ReminderSendResult; err?: string } | null>(null)

  async function sendNow(streamId: number) {
    setSending(streamId)
    setSendResult(null)
    try {
      const r = await sendReminderNow(companyId, streamId)
      setSendResult({ streamId, r })
      log.reload()
    } catch (e) {
      setSendResult({ streamId, err: errorText(e) })
    } finally {
      setSending(null)
    }
  }

  function describe(r: ReminderSendResult): string {
    if (!r.sent || r.sent.length === 0) return 'Nothing sent — no channel is switched on.'
    return r.sent
      .map((x) => {
        const ch = x.channel === 'whatsapp' ? 'WhatsApp' : 'Email'
        if (x.ok) return `${ch} → ${x.to}: sent`
        // Backend reports a missing channel as status skipped_not_configured with
        // an error like "SMTP_HOST not set" / "WA_PHONE_NUMBER_ID / WA_TOKEN not set".
        if (/not_configured|not set\b/i.test(`${(x as { status?: string }).status ?? ''} ${x.error ?? ''}`))
          return `${ch}: not set up on the server yet`
        return `${ch} → ${x.to}: failed${x.error ? ` (${x.error})` : ''}`
      })
      .join(' · ')
  }

  return (
    <div className="card">
      <h2 style={{ marginBottom: 4 }}>What will go out in the next 30 days</h2>
      <p className="muted small" style={{ margin: '0 0 10px' }}>
        Only licences with "Remind me" switched on are listed. Use "Send test now" to check your phone or inbox.
      </p>
      {preview.loading && !preview.data ? (
        <Loading />
      ) : preview.error ? (
        <ErrorMsg>{preview.error}</ErrorMsg>
      ) : !preview.data || preview.data.length === 0 ? (
        <Empty title="No reminders in the next 30 days">
          Switch on "Remind me before this is due" on a <Link to="/lines">licence</Link> and enable a channel above.
        </Empty>
      ) : (
        <div className="table-wrap cards">
          <table>
            <thead>
              <tr>
                <th>Licence</th>
                <th className="right">Amount</th>
                <th>Due</th>
                <th>Reminder goes on</th>
                <th>How</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {preview.data.map((r) => (
                <tr key={`${r.stream_id}-${r.due}-${r.days_before}`}>
                  <td className="cell-primary" data-label="Licence">
                    <Link to={`/lines?open=${r.stream_id}`}>
                      <strong>{r.vendor_name}</strong>
                    </Link>
                    {r.product ? <span className="muted"> · {r.product}</span> : null}
                  </td>
                  <td className="right num" data-label="Amount">{rupees(r.amount)}</td>
                  <td data-label="Due">{fmtDate(r.due)}</td>
                  <td data-label="Reminder goes on">
                    {fmtDate(r.will_send_on)} <span className="muted small">({r.days_before} days before)</span>
                  </td>
                  <td data-label="How">
                    {r.channel.length ? r.channel.map((c) => (c === 'whatsapp' ? 'WhatsApp' : 'Email')).join(' + ') : '—'}
                  </td>
                  <td data-label="">
                    {canEdit && (
                      <button
                        className="btn btn-sm"
                        disabled={sending !== null}
                        onClick={() => sendNow(r.stream_id)}
                      >
                        {sending === r.stream_id ? 'Sending…' : 'Send test now'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sendResult && (
        <div style={{ marginTop: 10 }}>
          {sendResult.err ? (
            <ErrorMsg>{sendResult.err}</ErrorMsg>
          ) : (
            <div className={`msg ${sendResult.r && sendResult.r.sent.some((x) => x.ok) ? 'msg-ok' : 'msg-warn'}`}>
              {sendResult.r ? describe(sendResult.r) : null}
            </div>
          )}
        </div>
      )}

      <h3 style={{ margin: '18px 0 8px' }}>Reminder log</h3>
      {log.loading && !log.data ? (
        <Loading />
      ) : log.error ? (
        <ErrorMsg>{log.error}</ErrorMsg>
      ) : !log.data || log.data.length === 0 ? (
        <div className="muted small">Nothing sent yet.</div>
      ) : (
        <div className="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Licence</th>
                <th>How</th>
                <th>To</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {log.data.map((l) => (
                <tr key={l.id} title={l.message}>
                  <td>{fmtDateTime(l.sent_at)}</td>
                  <td>{l.vendor_name}</td>
                  <td>{l.channel === 'whatsapp' ? 'WhatsApp' : 'Email'}</td>
                  <td>{l.to}</td>
                  <td>
                    {l.status === 'skipped_not_configured' ? (
                      <span className="pill pill-amber">Not set up on the server yet</span>
                    ) : /fail|error/i.test(l.status) ? (
                      <span className="pill pill-red">{humanize(l.status)}</span>
                    ) : (
                      <span className="pill pill-green">{humanize(l.status)}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Aliases({ companyId, canEdit }: { companyId: number; canEdit: boolean }) {
  const aliases = useFetch(() => listAliases(companyId), [companyId])
  const [removing, setRemoving] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)

  async function remove(id: number) {
    setRemoving(id)
    setErr(null)
    try {
      await deleteAlias(companyId, id)
      aliases.setData((prev) => (prev ? prev.filter((a) => a.id !== id) : prev))
      notifyDataChanged() // the server re-checks everything after an undo
    } catch (e) {
      setErr(errorText(e))
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginBottom: 4 }}>Hidden payees &amp; learned answers</h2>
      <p className="muted small" style={{ margin: '0 0 10px' }}>
        Every time you answer "what is this?" or hide a payee, we remember it here. Remove a row to undo — the payee will
        be asked about again.
      </p>
      {err && (
        <div style={{ marginBottom: 10 }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
      {aliases.loading && !aliases.data ? (
        <Loading />
      ) : aliases.error ? (
        <ErrorMsg>{aliases.error}</ErrorMsg>
      ) : !aliases.data || aliases.data.length === 0 ? (
        <Empty title="Nothing learned yet">Answers from the Attention page will show up here.</Empty>
      ) : (
        <div className="table-wrap cards">
          <table>
            <thead>
              <tr>
                <th>Payee text</th>
                <th>We treat it as</th>
                <th>Since</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {aliases.data.map((a) => (
                <tr key={a.id}>
                  <td className="cell-primary" data-label="Payee">
                    <strong>{a.pattern}</strong>
                  </td>
                  <td data-label="We treat it as">
                    {a.hidden ? (
                      <span className="pill pill-grey">Hidden (not IT)</span>
                    ) : (
                      <>
                        {a.vendor_name ?? '—'}
                        {a.product ? <span className="muted"> · {a.product}</span> : null}
                      </>
                    )}
                  </td>
                  <td data-label="Since">{fmtDate(a.created_at)}</td>
                  <td data-label="">
                    {canEdit && (
                      <button className="btn btn-sm" disabled={removing !== null} onClick={() => remove(a.id)}>
                        {removing === a.id ? 'Removing…' : 'Remove (undo)'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Invite({ companyId }: { companyId: number }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('accountant')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<InviteResult | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setResult(null)
    if (!email.trim()) return setErr('Enter an email address.')
    setBusy(true)
    try {
      const r = await inviteUser({ company_id: companyId, email: email.trim(), role })
      setResult(r)
      setEmail('')
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 style={{ marginBottom: 4 }}>Invite a user</h2>
      <p className="muted small" style={{ margin: '0 0 10px' }}>
        Add your accountant or a colleague. We show a one-time password here — pass it on yourself (no email is sent).
      </p>
      <div className="form-row">
        <label className="field">
          <span>Email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          <span>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {humanize(r)} — {ROLE_HELP[r]}
              </option>
            ))}
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
          {busy ? 'Inviting…' : 'Invite'}
        </button>
      </div>
      {result && (
        <div className="msg msg-ok" style={{ marginTop: 12 }}>
          <div>
            <strong>{result.email}</strong> added as {humanize(result.role)}.
          </div>
          {result.temp_password ? (
            <div style={{ marginTop: 6 }}>
              Temporary password: <code className="mono temp-pw">{result.temp_password}</code>
              <div className="small" style={{ marginTop: 4 }}>
                Shown only once — copy it now and share it with them.
              </div>
            </div>
          ) : (
            <div className="small" style={{ marginTop: 4 }}>They already had an account; they can log in with their existing password.</div>
          )}
        </div>
      )}
    </form>
  )
}

function DeleteCompany({ companyId, companyName }: { companyId: number; companyName: string }) {
  const navigate = useNavigate()
  const { reload, select, companies } = useCompany()
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const match = typed.trim() === companyName.trim() && companyName.trim() !== ''

  async function doDelete() {
    if (!match) return
    setBusy(true)
    setErr(null)
    try {
      await deleteCompany(companyId)
      const other = companies.find((c) => c.id !== companyId)
      if (other) select(other.id)
      await reload()
      navigate('/upload', { replace: true })
    } catch (e) {
      setErr(errorText(e))
      setBusy(false)
    }
  }

  return (
    <div className="card danger-zone">
      <h2 style={{ marginBottom: 4 }}>Delete this company</h2>
      <p className="muted small" style={{ margin: '0 0 10px' }}>
        Removes every statement, licence, payment, question and reminder for <strong>{companyName}</strong>. This cannot
        be undone.
      </p>
      {!open ? (
        <button className="btn btn-danger" onClick={() => setOpen(true)}>
          Delete this company…
        </button>
      ) : (
        <div>
          <label className="field">
            <span>Type the company name to confirm: {companyName}</span>
            <input type="text" value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
          </label>
          {err && (
            <div style={{ marginBottom: 10 }}>
              <ErrorMsg>{err}</ErrorMsg>
            </div>
          )}
          <div className="form-actions">
            <button className="btn btn-danger" disabled={!match || busy} onClick={doDelete}>
              {busy ? 'Deleting…' : 'Yes, delete everything'}
            </button>
            <button className="btn" disabled={busy} onClick={() => { setOpen(false); setTyped('') }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
