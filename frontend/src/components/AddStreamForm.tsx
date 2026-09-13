import { useState } from 'react'
import { createStream, CYCLES, type Cycle, type StreamCreate, type StreamOut } from '../lib/api'
import { errorText } from '../lib/useFetch'
import { notifyDataChanged } from '../lib/events'
import { CYCLE_LABEL } from '../lib/format'
import { ErrorMsg } from './ui'

const SUGGESTED_CATEGORIES = [
  'accounting',
  'erp',
  'email',
  'office',
  'design',
  'security',
  'cloud',
  'domain_hosting',
  'communication',
  'hr_payroll',
  'compliance',
  'amc',
  'hardware',
  'other',
]

interface Props {
  companyId: number
  categories: string[]
  onCreated: (s: StreamOut) => void
  onCancel: () => void
}

export default function AddStreamForm({ companyId, categories, onCreated, onCancel }: Props) {
  const [f, setF] = useState({
    vendor_name: '',
    product: '',
    category: '',
    cycle: 'yearly' as Cycle,
    expected_amount: '',
    next_due: '',
    last_paid_date: '',
    auto_renew: false,
    paid_from: '',
    owner_name: '',
    pay_url: '',
    notes: '',
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const cats = Array.from(new Set([...categories, ...SUGGESTED_CATEGORIES])).sort()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    const amount = Number(f.expected_amount)
    if (!f.vendor_name.trim()) return setErr('Vendor name is required.')
    if (!f.product.trim()) return setErr('Product is required.')
    if (!f.category) return setErr('Pick a category.')
    if (f.expected_amount.trim() === '' || Number.isNaN(amount) || amount < 0)
      return setErr('Expected amount must be a number.')
    const body: StreamCreate = {
      vendor_name: f.vendor_name.trim(),
      product: f.product.trim(),
      category: f.category,
      cycle: f.cycle,
      expected_amount: amount,
      auto_renew: f.auto_renew,
    }
    if (f.next_due) body.next_due = f.next_due
    if (f.last_paid_date) body.last_paid_date = f.last_paid_date
    if (f.paid_from.trim()) body.paid_from = f.paid_from.trim()
    if (f.owner_name.trim()) body.owner_name = f.owner_name.trim()
    if (f.pay_url.trim()) body.pay_url = f.pay_url.trim()
    if (f.notes.trim()) body.notes = f.notes.trim()
    setBusy(true)
    try {
      const s = await createStream(companyId, body)
      notifyDataChanged()
      onCreated(s)
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="row" style={{ marginBottom: 10 }}>
        <h2>Add licence</h2>
        <span className="spacer" />
        <button type="button" className="btn btn-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <div className="form-row">
        <label className="field">
          <span>Vendor name *</span>
          <input
            type="text"
            value={f.vendor_name}
            onChange={(e) => setF({ ...f, vendor_name: e.target.value })}
            placeholder="Tally Solutions"
            required
          />
        </label>
        <label className="field">
          <span>Product *</span>
          <input
            type="text"
            value={f.product}
            onChange={(e) => setF({ ...f, product: e.target.value })}
            placeholder="TallyPrime Silver TSS"
            required
          />
        </label>
        <label className="field">
          <span>Category *</span>
          <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} required>
            <option value="">Select…</option>
            {cats.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Billing cycle *</span>
          <select value={f.cycle} onChange={(e) => setF({ ...f, cycle: e.target.value as Cycle })}>
            {CYCLES.map((c) => (
              <option key={c} value={c}>
                {CYCLE_LABEL[c]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Expected amount (₹) *</span>
          <input
            type="number"
            step="0.01"
            min="0"
            value={f.expected_amount}
            onChange={(e) => setF({ ...f, expected_amount: e.target.value })}
            required
          />
        </label>
        <label className="field">
          <span>Next due</span>
          <input type="date" value={f.next_due} onChange={(e) => setF({ ...f, next_due: e.target.value })} />
        </label>
        <label className="field">
          <span>Last paid</span>
          <input
            type="date"
            value={f.last_paid_date}
            onChange={(e) => setF({ ...f, last_paid_date: e.target.value })}
          />
        </label>
        <label className="field">
          <span>Paid from</span>
          <input
            type="text"
            value={f.paid_from}
            onChange={(e) => setF({ ...f, paid_from: e.target.value })}
            placeholder="HDFC Current"
          />
        </label>
        <label className="field">
          <span>Owner</span>
          <input
            type="text"
            value={f.owner_name}
            onChange={(e) => setF({ ...f, owner_name: e.target.value })}
          />
        </label>
        <label className="field">
          <span>Pay link</span>
          <input type="url" value={f.pay_url} onChange={(e) => setF({ ...f, pay_url: e.target.value })} />
        </label>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={f.auto_renew}
          onChange={(e) => setF({ ...f, auto_renew: e.target.checked })}
        />
        Auto-renews (charged automatically)
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
      </label>
      {err && (
        <div style={{ marginBottom: 10 }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Adding…' : 'Add licence'}
        </button>
      </div>
    </form>
  )
}
