import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  answerBulk,
  answerQuestion,
  listQuestions,
  listVendors,
  type Question,
  type SplitItem,
} from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged, useDataChanged } from '../lib/events'
import { fmtDate, rupees, CYCLE_LABEL, sourceLabel } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany } from '../components/ui'

const KIND_LABEL: Record<Question['kind'], string> = {
  vendor: 'Which software is this?',
  cycle: 'How often is this paid?',
  split: 'One payment, several things?',
  stopped: 'Stopped paying?',
  bundle: 'What did this reseller bill cover?',
}

const SPLIT_KEY = /^split/i

export default function Attention() {
  const { companyId, canEdit } = useCompany()
  const qs = useFetch(() => listQuestions(companyId as number, true), [companyId], companyId !== null)
  useDataChanged(qs.reload)

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkChoice, setBulkChoice] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkErr, setBulkErr] = useState<string | null>(null)
  const [bulkOk, setBulkOk] = useState<string | null>(null)

  // Only answers every selected question offers can be applied to all of them.
  const commonOptions = useMemo(() => {
    const list = (qs.data ?? []).filter((q) => selected.has(q.id))
    if (list.length === 0) return []
    let keys = new Set(list[0].options.map((o) => o.key))
    for (const q of list.slice(1)) keys = new Set(q.options.filter((o) => keys.has(o.key)).map((o) => o.key))
    return list[0].options.filter((o) => keys.has(o.key) && !SPLIT_KEY.test(o.key))
  }, [qs.data, selected])

  if (companyId === null) return <NoCompany />

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function sendBulk() {
    if (!bulkChoice || selected.size === 0) return
    setBulkBusy(true)
    setBulkErr(null)
    setBulkOk(null)
    try {
      const ids = Array.from(selected)
      const r = await answerBulk(
        companyId as number,
        ids.map((question_id) => ({ question_id, choice: bulkChoice })),
      )
      qs.setData((prev) => (prev ? prev.filter((q) => !selected.has(q.id)) : prev))
      setSelected(new Set())
      setBulkChoice('')
      setBulkOk(`Answered ${r.answered} question${r.answered === 1 ? '' : 's'}.`)
      notifyDataChanged()
    } catch (e) {
      setBulkErr(errorText(e))
    } finally {
      setBulkBusy(false)
    }
  }

  const list = qs.data ?? []

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Needs attention</h1>
          <p>Quick answers so every payment lands on the right licence.</p>
        </div>
        <button className="btn btn-sm" onClick={qs.reload} disabled={qs.loading}>
          Refresh
        </button>
      </div>

      {!canEdit && list.length > 0 && (
        <div className="msg msg-muted">You have view-only access — an owner or accountant needs to answer these.</div>
      )}

      {canEdit && list.length > 1 && (
        <div className="bulk-bar">
          <label className="check" style={{ marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={selected.size === list.length}
              onChange={(e) => setSelected(e.target.checked ? new Set(list.map((q) => q.id)) : new Set())}
            />
            {selected.size > 0 ? `${selected.size} selected` : 'Select all'}
          </label>
          {selected.size > 0 && (
            <>
              <span className="muted small">Answer selected as…</span>
              <select
                value={bulkChoice}
                onChange={(e) => setBulkChoice(e.target.value)}
                style={{ width: 'auto', maxWidth: 280 }}
                disabled={commonOptions.length === 0}
              >
                <option value="">
                  {commonOptions.length === 0 ? 'These questions have no answer in common' : 'Choose an answer'}
                </option>
                {commonOptions.map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
              </select>
              <button className="btn btn-sm btn-primary" disabled={!bulkChoice || bulkBusy} onClick={sendBulk}>
                {bulkBusy ? 'Saving…' : `Apply to ${selected.size}`}
              </button>
              <button className="btn btn-sm" disabled={bulkBusy} onClick={() => setSelected(new Set())}>
                Clear
              </button>
            </>
          )}
        </div>
      )}
      {bulkOk && <div className="msg msg-ok">{bulkOk}</div>}
      {bulkErr && <ErrorMsg>{bulkErr}</ErrorMsg>}

      {qs.loading && !qs.data ? (
        <Loading text="Loading questions…" />
      ) : qs.error ? (
        <ErrorMsg>{qs.error}</ErrorMsg>
      ) : list.length === 0 ? (
        <div className="card">
          <Empty title="Nothing to check — all clear">
            New questions appear here after you <Link to="/upload">upload a statement</Link>.
          </Empty>
        </div>
      ) : (
        <div>
          {list.map((q) => (
            <QuestionCard
              key={q.id}
              companyId={companyId}
              q={q}
              canEdit={canEdit}
              selectable={list.length > 1}
              selected={selected.has(q.id)}
              onToggle={() => toggle(q.id)}
              onAnswered={() => {
                qs.setData((prev) => (prev ? prev.filter((x) => x.id !== q.id) : prev))
                setSelected((prev) => {
                  const next = new Set(prev)
                  next.delete(q.id)
                  return next
                })
                notifyDataChanged()
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function QuestionCard({
  companyId,
  q,
  canEdit,
  selectable,
  selected,
  onToggle,
  onAnswered,
}: {
  companyId: number
  q: Question
  canEdit: boolean
  selectable: boolean
  selected: boolean
  onToggle: () => void
  onAnswered: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [pendingChoice, setPendingChoice] = useState<string | null>(null)
  const [splitting, setSplitting] = useState<string | null>(null)

  const ctx = q.context ?? {}
  const dates = Array.isArray(ctx.dates) ? (ctx.dates as string[]) : []
  const sources = Array.isArray(ctx.sources) ? (ctx.sources as string[]) : []
  const cycleGuess = typeof ctx.cycle_guess === 'string' ? ctx.cycle_guess : null
  // Any other scalar context fields we don't specifically know about.
  const extra = Object.entries(ctx).filter(
    ([k, v]) =>
      !['payee', 'amount', 'dates', 'sources', 'cycle_guess'].includes(k) &&
      (typeof v === 'string' || typeof v === 'number'),
  )

  // Heuristic: an option whose key/label mentions "other"/"type"/"enter" needs free text.
  const needsText = (key: string, label: string) =>
    /other|type|enter|name it|custom|specify/i.test(key + ' ' + label)

  async function send(choice: string, freeText?: string, items?: SplitItem[]) {
    setBusy(choice)
    setErr(null)
    try {
      await answerQuestion(companyId, q.id, {
        choice,
        ...(freeText ? { text: freeText } : {}),
        ...(items ? { items } : {}),
      })
      onAnswered()
    } catch (e) {
      setErr(errorText(e))
      setBusy(null)
    }
  }

  return (
    <div className={`question${selected ? ' is-selected' : ''}`}>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        {canEdit && selectable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label="Select this question"
            style={{ marginTop: 3 }}
          />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="kind">{KIND_LABEL[q.kind] ?? q.kind}</div>
          <div className="prompt">{q.prompt}</div>
        </div>
      </div>
      <div className="ctx">
        {ctx.payee ? (
          <span>
            Payee: <strong>{String(ctx.payee)}</strong>
          </span>
        ) : null}
        {typeof ctx.amount === 'number' ? (
          <span>
            Amount: <strong className="num">{rupees(ctx.amount, { decimals: true })}</strong>
          </span>
        ) : null}
        {dates.length > 0 ? (
          <span>
            Dates: {dates.slice(0, 6).map(fmtDate).join(', ')}
            {dates.length > 6 ? ` +${dates.length - 6} more` : ''}
          </span>
        ) : null}
        {cycleGuess ? (
          <span>Our guess: {(CYCLE_LABEL as Record<string, string>)[cycleGuess] ?? cycleGuess}</span>
        ) : null}
        {sources.length > 0 ? <span>Seen in: {sources.map(sourceLabel).join(' · ')}</span> : null}
        {extra.map(([k, v]) => (
          <span key={k}>
            {k.replace(/_/g, ' ')}: {String(v)}
          </span>
        ))}
        {q.stream_id ? <Link to={`/lines?open=${q.stream_id}`}>View licence</Link> : null}
      </div>

      {!canEdit ? null : splitting !== null ? (
        <SplitForm
          total={typeof ctx.amount === 'number' ? ctx.amount : null}
          busy={busy !== null}
          onCancel={() => setSplitting(null)}
          onSubmit={(items) => send(splitting, undefined, items)}
        />
      ) : pendingChoice === null ? (
        <div className="options">
          {q.options.map((o) => {
            const isSplit = q.kind === 'bundle' && SPLIT_KEY.test(o.key)
            return (
              <button
                key={o.key}
                className="btn btn-sm"
                disabled={busy !== null}
                onClick={() =>
                  isSplit
                    ? setSplitting(o.key)
                    : needsText(o.key, o.label)
                      ? setPendingChoice(o.key)
                      : send(o.key)
                }
              >
                {busy === o.key ? 'Saving…' : o.label}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="row" style={{ marginTop: 12 }}>
          <input
            type="text"
            style={{ width: 'auto', flex: '1 1 200px' }}
            placeholder="Type the name…"
            value={text}
            autoFocus
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && text.trim()) send(pendingChoice, text.trim())
            }}
          />
          <button
            className="btn btn-sm btn-primary"
            disabled={busy !== null || !text.trim()}
            onClick={() => send(pendingChoice, text.trim())}
          >
            {busy ? 'Saving…' : 'Submit'}
          </button>
          <button className="btn btn-sm" disabled={busy !== null} onClick={() => setPendingChoice(null)}>
            Back
          </button>
        </div>
      )}
      {err && (
        <div style={{ marginTop: 10 }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
    </div>
  )
}

interface SplitRow {
  vendor_key: string
  product: string
  amount: string
}

/** Tiny inline form for "Split into several": one row per product on the reseller's bill. */
function SplitForm({
  total,
  busy,
  onCancel,
  onSubmit,
}: {
  total: number | null
  busy: boolean
  onCancel: () => void
  onSubmit: (items: SplitItem[]) => void
}) {
  const [rows, setRows] = useState<SplitRow[]>([
    { vendor_key: '', product: '', amount: '' },
    { vendor_key: '', product: '', amount: '' },
  ])
  const [err, setErr] = useState<string | null>(null)
  const vendors = useFetch(() => listVendors(), [])

  const sum = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0)
  const remaining = total != null ? total - sum : null

  function update(i: number, patch: Partial<SplitRow>) {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  }

  function submit() {
    setErr(null)
    const items: SplitItem[] = []
    for (const r of rows) {
      if (!r.vendor_key.trim() && !r.product.trim() && !r.amount.trim()) continue // blank row
      const amount = Number(r.amount)
      if (!r.vendor_key.trim()) return setErr('Each row needs a vendor.')
      if (!r.product.trim()) return setErr('Each row needs a product name.')
      if (Number.isNaN(amount) || amount <= 0) return setErr('Each row needs an amount greater than 0.')
      items.push({ vendor_key: r.vendor_key.trim(), product: r.product.trim(), amount })
    }
    if (items.length < 2) return setErr('Add at least two rows to split into.')
    onSubmit(items)
  }

  return (
    <div className="split-form">
      <div className="muted small" style={{ marginBottom: 6 }}>
        What did this bill cover? One row per product.
        {total != null ? (
          <>
            {' '}
            Total <span className="num">{rupees(total, { decimals: true })}</span>
            {remaining != null && Math.abs(remaining) >= 1 ? (
              <>
                {' '}· <span className="num">{rupees(Math.abs(remaining), { decimals: true })}</span>{' '}
                {remaining > 0 ? 'left to allocate' : 'over the total'}
              </>
            ) : null}
          </>
        ) : null}
      </div>
      <datalist id="split-vendors">
        {(vendors.data ?? []).map((v) => (
          <option key={v.key} value={v.key}>
            {v.name}
          </option>
        ))}
      </datalist>
      {rows.map((r, i) => (
        <div key={i} className="split-row">
          <input
            type="text"
            list="split-vendors"
            placeholder="Vendor (e.g. microsoft365)"
            value={r.vendor_key}
            onChange={(e) => update(i, { vendor_key: e.target.value })}
          />
          <input
            type="text"
            placeholder="Product (e.g. Business Standard × 10)"
            value={r.product}
            onChange={(e) => update(i, { product: e.target.value })}
          />
          <input
            type="number"
            step="0.01"
            min="0"
            placeholder="₹"
            value={r.amount}
            onChange={(e) => update(i, { amount: e.target.value })}
          />
          <button
            type="button"
            className="btn btn-sm"
            aria-label="Remove row"
            disabled={rows.length <= 2}
            onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
          >
            ×
          </button>
        </div>
      ))}
      {err && (
        <div style={{ margin: '6px 0' }}>
          <ErrorMsg>{err}</ErrorMsg>
        </div>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => setRows((prev) => [...prev, { vendor_key: '', product: '', amount: '' }])}
        >
          + Add row
        </button>
        <span className="spacer" />
        <button type="button" className="btn btn-sm" disabled={busy} onClick={onCancel}>
          Back
        </button>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={submit}>
          {busy ? 'Saving…' : 'Split'}
        </button>
      </div>
    </div>
  )
}
