import { useEffect, useRef, useState } from 'react'
import {
  confirmStream,
  getStream,
  markPaid,
  patchStream,
  CYCLES,
  type StreamDetail,
  type StreamOut,
  type StreamPatch,
  type Cycle,
} from '../lib/api'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged } from '../lib/events'
import { CYCLE_LABEL, fmtDate, rupees, todayISO, humanize, confidenceLabel, flagLabel } from '../lib/format'
import { ErrorMsg, Loading, SeenIn, Sources, StatusPill } from './ui'

interface Props {
  companyId: number
  streamId: number
  onClose: () => void
  /** Called whenever the stream changes so the parent list can update in place. */
  onChanged: (s: StreamOut) => void
  /** false for viewers: no Mark paid / edit controls. */
  canEdit?: boolean
}

interface EditForm {
  vendor_name: string
  product: string
  cycle: Cycle
  expected_amount: string
  next_due: string
  owner_name: string
  paid_from: string
  pay_url: string
  reminder_on: boolean
  notes: string
}

// Lines that no longer recur: the old next-due date would only mislead.
const ENDED = new Set(['cancelled', 'stopped', 'dismissed', 'one_time'])

function toForm(s: StreamOut): EditForm {
  return {
    vendor_name: s.vendor_name ?? '',
    product: s.product ?? '',
    cycle: s.cycle,
    expected_amount: s.expected_amount === null || s.expected_amount === undefined ? '' : String(s.expected_amount),
    next_due: s.next_due ?? '',
    owner_name: s.owner_name ?? '',
    paid_from: s.paid_from ?? '',
    pay_url: s.pay_url ?? '',
    reminder_on: !!s.reminder_on,
    notes: s.notes ?? '',
  }
}

export default function StreamDrawer({ companyId, streamId, onClose, onChanged, canEdit = true }: Props) {
  const detail = useFetch(() => getStream(companyId, streamId), [companyId, streamId])
  const [form, setForm] = useState<EditForm | null>(null)
  const [showDetails, setShowDetails] = useState(!canEdit)
  const [saving, setSaving] = useState(false)
  const [saveErr, setSaveErr] = useState<string | null>(null)
  const [saveOk, setSaveOk] = useState(false)

  const [payDate, setPayDate] = useState(todayISO())
  const [payAmount, setPayAmount] = useState('')
  const [paying, setPaying] = useState(false)
  const [payErr, setPayErr] = useState<string | null>(null)

  const [confirming, setConfirming] = useState(false)
  const [confirmErr, setConfirmErr] = useState<string | null>(null)

  useEffect(() => {
    if (detail.data) {
      setForm(toForm(detail.data))
      setPayAmount(detail.data.expected_amount != null ? String(detail.data.expected_amount) : '')
    }
  }, [detail.data])

  // Keyboard: Esc closes; Tab cycles inside the dialog instead of escaping to
  // the page behind the backdrop; focus moves in on open and back out on close.
  const asideRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const focusables = () =>
      Array.from(
        asideRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => el.offsetParent !== null)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const els = focusables()
      if (els.length === 0) return
      const first = els[0]
      const last = els[els.length - 1]
      const active = document.activeElement as HTMLElement | null
      const inside = !!active && !!asideRef.current?.contains(active)
      if (!inside) {
        e.preventDefault()
        ;(e.shiftKey ? last : first).focus()
      } else if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      if (opener && document.contains(opener)) opener.focus()
    }
  }, [onClose])
  // Once content is in, put focus on the Close button (first control).
  useEffect(() => {
    if (!form) return // the loaded view (and its Close button) renders once the form exists
    const btn = asideRef.current?.querySelector<HTMLElement>('.close-btn')
    if (btn && !asideRef.current?.contains(document.activeElement)) btn.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form !== null])

  const s = detail.data

  function applyUpdate(updated: StreamOut) {
    // Merge into detail so occurrences/amount_history are preserved.
    detail.setData((prev) => (prev ? { ...prev, ...updated } : (updated as StreamDetail)))
    onChanged(updated)
    notifyDataChanged()
  }

  async function save() {
    if (!s || !form) return
    setSaving(true)
    setSaveErr(null)
    setSaveOk(false)
    const body: StreamPatch = {}
    if (form.vendor_name !== (s.vendor_name ?? '')) body.vendor_name = form.vendor_name
    if (form.product !== (s.product ?? '')) body.product = form.product || null
    if (form.cycle !== s.cycle) body.cycle = form.cycle
    const amt = form.expected_amount.trim() === '' ? null : Number(form.expected_amount)
    if (amt !== (s.expected_amount ?? null)) {
      if (amt !== null && Number.isNaN(amt)) {
        setSaveErr('Expected amount must be a number.')
        setSaving(false)
        return
      }
      body.expected_amount = amt
    }
    if (form.next_due !== (s.next_due ?? '')) body.next_due = form.next_due || null
    if (form.owner_name !== (s.owner_name ?? '')) body.owner_name = form.owner_name || null
    if (form.paid_from !== (s.paid_from ?? '')) body.paid_from = form.paid_from || null
    if (form.pay_url !== (s.pay_url ?? '')) body.pay_url = form.pay_url || null
    if (form.reminder_on !== !!s.reminder_on) body.reminder_on = form.reminder_on
    if (form.notes !== (s.notes ?? '')) body.notes = form.notes || null

    if (Object.keys(body).length === 0) {
      setSaving(false)
      setSaveOk(true)
      return
    }
    try {
      const updated = await patchStream(companyId, s.id, body)
      applyUpdate(updated)
      setSaveOk(true)
    } catch (e) {
      setSaveErr(errorText(e))
    } finally {
      setSaving(false)
    }
  }

  async function doMarkPaid() {
    if (!s) return
    setPaying(true)
    setPayErr(null)
    try {
      const body: { date: string; amount?: number } = { date: payDate }
      if (payAmount.trim() !== '') {
        const n = Number(payAmount)
        if (Number.isNaN(n)) throw new Error('Amount must be a number.')
        body.amount = n
      }
      const updated = await markPaid(companyId, s.id, body)
      applyUpdate(updated)
      detail.reload() // pull the new occurrence into history
    } catch (e) {
      setPayErr(errorText(e))
    } finally {
      setPaying(false)
    }
  }

  async function doConfirm(accept: boolean) {
    if (!s) return
    setConfirming(true)
    setConfirmErr(null)
    try {
      const updated = await confirmStream(companyId, s.id, accept)
      applyUpdate(updated)
    } catch (e) {
      setConfirmErr(errorText(e))
    } finally {
      setConfirming(false)
    }
  }

  const dirty = s && form ? JSON.stringify(form) !== JSON.stringify(toForm(s)) : false

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside ref={asideRef} className="drawer" role="dialog" aria-modal="true" aria-label="Licence details">
        {detail.loading && !s ? (
          <Loading />
        ) : detail.error ? (
          <>
            <div className="drawer-head">
              <h2>Licence</h2>
              <button className="close-btn" onClick={onClose}>
                Close
              </button>
            </div>
            <ErrorMsg>{detail.error}</ErrorMsg>
          </>
        ) : s && form ? (
          <>
            <div className="drawer-head">
              <div>
                <h2>
                  {s.vendor_name}
                  {s.product ? <span className="muted"> · {s.product}</span> : null}
                </h2>
                <div className="drawer-sub row">
                  <StatusPill status={s.status} />
                  <span>{humanize(s.category) === '—' ? 'Uncategorised' : humanize(s.category)}</span>
                  <span>·</span>
                  <span>{humanize(s.stream_type)}</span>
                  {s.payee_name && s.payee_name !== s.vendor_name ? (
                    <span className="muted">· paid to {s.payee_name}</span>
                  ) : null}
                </div>
              </div>
              <button className="close-btn" onClick={onClose}>
                Close
              </button>
            </div>

            {s.status === 'needs_confirm' && canEdit && (
              <div className="msg msg-warn" style={{ marginBottom: 12 }}>
                <div style={{ marginBottom: 8 }}>
                  Is this a subscription? We think this payment repeats.
                </div>
                <div className="row">
                  <button
                    className="btn btn-sm btn-primary"
                    disabled={confirming}
                    onClick={() => doConfirm(true)}
                  >
                    Yes, this repeats
                  </button>
                  <button className="btn btn-sm" disabled={confirming} onClick={() => doConfirm(false)}>
                    No, hide this payee
                  </button>
                  <span className="small muted">(undo in Settings)</span>
                </div>
                {confirmErr && (
                  <div style={{ marginTop: 8 }}>
                    <ErrorMsg>{confirmErr}</ErrorMsg>
                  </div>
                )}
              </div>
            )}

            <div className="summary-line">
              <span>
                <span className="muted">Amount</span> <strong className="num">{rupees(s.expected_amount ?? s.avg_amount, { decimals: true })}</strong>
              </span>
              <span>
                <span className="muted">How often</span> {CYCLE_LABEL[s.cycle] ?? s.cycle}
              </span>
              <span>
                <span className="muted">Next due</span>{' '}
                {ENDED.has(s.status) ? <span className="muted">— ({humanize(s.status)})</span> : fmtDate(s.next_due)}
              </span>
              <span>
                <span className="muted">Last paid</span> {fmtDate(s.last_paid_date)}
              </span>
            </div>
            {s.change_note && <div className="msg msg-muted" style={{ marginTop: 10 }}>{s.change_note}</div>}

            {canEdit && (
              <div className="section">
                <h3>Mark paid</h3>
                <div className="row" style={{ alignItems: 'flex-end' }}>
                  <label className="field" style={{ marginBottom: 0 }}>
                    <span>Paid on</span>
                    <input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} />
                  </label>
                  <label className="field" style={{ marginBottom: 0 }}>
                    <span>Amount (optional)</span>
                    <input
                      type="number"
                      step="0.01"
                      value={payAmount}
                      onChange={(e) => setPayAmount(e.target.value)}
                      placeholder="expected"
                    />
                  </label>
                  <button className="btn btn-primary" disabled={paying || !payDate} onClick={doMarkPaid}>
                    {paying ? 'Saving…' : 'Mark paid'}
                  </button>
                  {s.pay_url && (
                    <a className="btn" href={s.pay_url} target="_blank" rel="noopener noreferrer">
                      Pay now
                    </a>
                  )}
                </div>
                {payErr && (
                  <div style={{ marginTop: 8 }}>
                    <ErrorMsg>{payErr}</ErrorMsg>
                  </div>
                )}
              </div>
            )}
            {!canEdit && s.pay_url && (
              <div className="section">
                <a className="btn" href={s.pay_url} target="_blank" rel="noopener noreferrer">
                  Pay now
                </a>
              </div>
            )}

            {canEdit && (
            <div className="section">
              <h3>Edit</h3>
              <div className="form-row">
                <label className="field">
                  <span>Vendor name</span>
                  <input
                    type="text"
                    value={form.vendor_name}
                    onChange={(e) => setForm({ ...form, vendor_name: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Product</span>
                  <input
                    type="text"
                    value={form.product}
                    onChange={(e) => setForm({ ...form, product: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>How often</span>
                  <select
                    value={form.cycle}
                    onChange={(e) => setForm({ ...form, cycle: e.target.value as Cycle })}
                  >
                    {CYCLES.map((c) => (
                      <option key={c} value={c}>
                        {CYCLE_LABEL[c]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Expected amount (₹)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={form.expected_amount}
                    onChange={(e) => setForm({ ...form, expected_amount: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Next due</span>
                  <input
                    type="date"
                    value={form.next_due}
                    onChange={(e) => setForm({ ...form, next_due: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Owner</span>
                  <input
                    type="text"
                    value={form.owner_name}
                    onChange={(e) => setForm({ ...form, owner_name: e.target.value })}
                    placeholder="Who looks after this"
                  />
                </label>
                <label className="field">
                  <span>Paid from</span>
                  <input
                    type="text"
                    value={form.paid_from}
                    onChange={(e) => setForm({ ...form, paid_from: e.target.value })}
                    placeholder="HDFC Current, MD card…"
                  />
                </label>
                <label className="field">
                  <span>Pay link</span>
                  <input
                    type="url"
                    value={form.pay_url}
                    onChange={(e) => setForm({ ...form, pay_url: e.target.value })}
                    placeholder="https://…"
                  />
                </label>
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={form.reminder_on}
                  onChange={(e) => setForm({ ...form, reminder_on: e.target.checked })}
                />
                Remind me before this is due
              </label>
              <label className="field">
                <span>Notes</span>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </label>
              <div className="form-actions">
                <button className="btn btn-primary" disabled={saving || !dirty} onClick={save}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
                {dirty && (
                  <button className="btn" disabled={saving} onClick={() => setForm(toForm(s))}>
                    Discard
                  </button>
                )}
                {saveOk && !dirty && <span className="small" style={{ color: 'var(--ok)' }}>Saved.</span>}
                {s.is_user_modified && (
                  <span className="small muted">Edited by you — we won't change these fields on re-check.</span>
                )}
              </div>
              {saveErr && (
                <div style={{ marginTop: 8 }}>
                  <ErrorMsg>{saveErr}</ErrorMsg>
                </div>
              )}
            </div>
            )}

            <div className="section">
              <button
                type="button"
                className="btn-link details-toggle"
                aria-expanded={showDetails}
                onClick={() => setShowDetails((v) => !v)}
              >
                {showDetails ? '▾' : '▸'} Details
              </button>
              {showDetails && (
                <dl className="kv" style={{ marginTop: 8 }}>
                  <dt>Average paid</dt>
                  <dd className="num">{rupees(s.avg_amount, { decimals: true })}</dd>
                  <dt>Per month</dt>
                  <dd className="num">{rupees(s.monthly_equivalent)}</dd>
                  {s.quantity != null && s.unit_price != null && (
                    <>
                      <dt>Seats</dt>
                      <dd className="num">
                        {s.quantity} {s.quantity === 1 ? 'user' : 'users'} × {rupees(s.unit_price, { decimals: true })}
                      </dd>
                    </>
                  )}
                  {s.rcm_gst != null && s.rcm_gst > 0 && (
                    <>
                      <dt>GST</dt>
                      <dd>You pay 18% GST on this yourself (reverse charge): ≈ {rupees(s.rcm_gst)}</dd>
                    </>
                  )}
                  <dt>Type</dt>
                  <dd>{humanize(s.stream_type)}</dd>
                  <dt>Auto-renews</dt>
                  <dd>{s.auto_renew === null || s.auto_renew === undefined ? '—' : s.auto_renew ? 'Yes' : 'No'}</dd>
                  <dt>How sure we are</dt>
                  <dd>
                    {confidenceLabel(s.confidence)} <span className="muted small">({s.confidence}%)</span>
                  </dd>
                  <dt>First seen</dt>
                  <dd>{fmtDate(s.first_seen)}</dd>
                  {s.fy && (
                    <>
                      <dt>Financial year</dt>
                      <dd>{s.fy}</dd>
                    </>
                  )}
                  <dt>Where we saw it</dt>
                  <dd>
                    <SeenIn sources={s.sources} />
                  </dd>
                  {s.supplier_history && s.supplier_history.length > 0 && (
                    <>
                      <dt>Supplier changed</dt>
                      <dd>{s.supplier_history.join(' → ')}</dd>
                    </>
                  )}
                  {((s.flags_human && s.flags_human.length > 0) || (s.flags && s.flags.length > 0)) && (
                    <>
                      <dt>Notes from us</dt>
                      <dd>
                        {(s.flags_human && s.flags_human.length > 0 ? s.flags_human : s.flags.map(flagLabel)).map(
                          (f, i) => (
                            <div key={i}>{f}</div>
                          ),
                        )}
                      </dd>
                    </>
                  )}
                </dl>
              )}
            </div>

            <div className="section">
              <h3>Payment history ({s.occurrences?.length ?? 0})</h3>
              {!s.occurrences || s.occurrences.length === 0 ? (
                <div className="muted small">No payments recorded yet.</div>
              ) : (
                <div className="table-wrap compact">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th className="right">Paid</th>
                        <th className="right">GST</th>
                        <th>Mode</th>
                        <th>Period</th>
                        <th>Seen in</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.occurrences.map((o) => (
                        <tr key={o.id} title={o.raw_description ?? undefined}>
                          <td>{fmtDate(o.date)}</td>
                          <td className="right num">
                            {rupees(o.amount_paid, { decimals: true })}
                            {o.currency && o.currency !== 'INR' && o.fx_amount != null ? (
                              <div className="cell-sub">
                                {o.currency} {o.fx_amount.toLocaleString('en-IN')}
                              </div>
                            ) : null}
                          </td>
                          <td className="right num">{o.gst != null ? rupees(o.gst, { decimals: true }) : '—'}</td>
                          <td>
                            {o.payment_mode ?? '—'}
                            {o.invoice_no ? <div className="cell-sub">Inv {o.invoice_no}</div> : null}
                          </td>
                          <td>
                            {o.period_from || o.period_to
                              ? `${fmtDate(o.period_from)} – ${fmtDate(o.period_to)}`
                              : '—'}
                          </td>
                          <td>
                            <Sources sources={o.sources} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {s.amount_history && s.amount_history.length > 0 && (
              <div className="section">
                <h3>Amount history</h3>
                <AmountHistory entries={s.amount_history} />
              </div>
            )}
          </>
        ) : null}
      </aside>
    </>
  )
}

function AmountHistory({ entries }: { entries: StreamDetail['amount_history'] }) {
  const rows = entries.map((e, i) =>
    typeof e === 'number' ? { key: i, date: null as string | null, amount: e } : { key: i, date: e.date ?? null, amount: e.amount },
  )
  const max = Math.max(1, ...rows.map((r) => r.amount))
  return (
    <div>
      {rows.map((r) => (
        <div key={r.key} className="bar-row">
          <span className="bar-label">{r.date ? fmtDate(r.date) : `#${r.key + 1}`}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${Math.max(2, (r.amount / max) * 100)}%` }} />
          </span>
          <span className="bar-val num">{rupees(r.amount)}</span>
        </div>
      ))}
    </div>
  )
}
