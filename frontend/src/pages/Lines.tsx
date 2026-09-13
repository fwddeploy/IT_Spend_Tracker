import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listStreams, markPaid, STATUSES, type StreamOut } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged, useDataChanged } from '../lib/events'
import { CYCLE_LABEL, STATUS_LABEL, fmtDate, rupees, humanize, todayISO } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany, Sources, StatusPill } from '../components/ui'
import StreamDrawer from '../components/StreamDrawer'
import AddStreamForm from '../components/AddStreamForm'

// Lines that no longer recur: a "next due" date is stale and misleading.
const ENDED = new Set(['cancelled', 'stopped', 'dismissed', 'one_time'])

export default function Lines() {
  const { companyId, canEdit } = useCompany()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const status = params.get('status') ?? ''
  const category = params.get('category') ?? ''
  const q = params.get('q') ?? ''
  const openId = params.get('open')
  const [adding, setAdding] = useState(false)

  // Bulk selection
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkDate, setBulkDate] = useState(todayISO())
  const [bulkBusy, setBulkBusy] = useState<{ done: number; total: number } | null>(null)
  const [bulkErr, setBulkErr] = useState<string | null>(null)
  const [bulkOk, setBulkOk] = useState<string | null>(null)

  // Fetch the full list once per company; filter client-side too so the table
  // stays responsive while typing. The server filters are passed through as well.
  const all = useFetch(() => listStreams(companyId as number), [companyId], companyId !== null)
  useDataChanged(all.reload)

  const categories = useMemo(() => {
    const set = new Set<string>()
    for (const s of all.data ?? []) if (s.category) set.add(s.category)
    return Array.from(set).sort()
  }, [all.data])

  const rows = useMemo(() => {
    let list = all.data ?? []
    if (status) list = list.filter((s) => s.status === status)
    if (category) list = list.filter((s) => (s.category ?? '') === category)
    if (q.trim()) {
      const needle = q.trim().toLowerCase()
      list = list.filter((s) =>
        [s.vendor_name, s.payee_name, s.product, s.category, s.paid_from, s.owner_name, s.notes]
          .filter(Boolean)
          .some((v) => String(v).toLowerCase().includes(needle)),
      )
    }
    return list
  }, [all.data, status, category, q])

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  // Opening a line pushes a history entry so the phone's Back button closes the
  // drawer instead of leaving the page. Closing pops that entry when we made it.
  const pushedOpen = useRef(false)
  function openLine(id: number) {
    const next = new URLSearchParams(params)
    next.set('open', String(id))
    pushedOpen.current = true
    setParams(next) // push
  }
  const closeDrawer = useCallback(() => {
    if (pushedOpen.current) {
      pushedOpen.current = false
      navigate(-1)
      return
    }
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('open')
        return next
      },
      { replace: true },
    )
  }, [setParams, navigate])
  useEffect(() => {
    if (!openId) pushedOpen.current = false
  }, [openId])

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  async function bulkMarkPaid() {
    const ids = Array.from(selected)
    if (ids.length === 0) return
    setBulkErr(null)
    setBulkOk(null)
    setBulkBusy({ done: 0, total: ids.length })
    let ok = 0
    const failed: string[] = []
    for (const id of ids) {
      try {
        const updated = await markPaid(companyId as number, id, { date: bulkDate })
        all.setData((prev) => (prev ? prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) : prev))
        ok++
      } catch (e) {
        const name = (all.data ?? []).find((s) => s.id === id)?.vendor_name ?? `#${id}`
        failed.push(`${name}: ${errorText(e)}`)
      }
      setBulkBusy({ done: ok + failed.length, total: ids.length })
    }
    setBulkBusy(null)
    setSelected(new Set())
    notifyDataChanged()
    if (ok) setBulkOk(`Marked ${ok} licence${ok === 1 ? '' : 's'} paid on ${fmtDate(bulkDate)}.`)
    if (failed.length) setBulkErr(failed.join(' · '))
  }

  // Switching company while a line is open would leave a dead "not found"
  // drawer (the id belongs to the other company) — close it instead.
  const prevCompany = useRef(companyId)
  useEffect(() => {
    if (prevCompany.current !== companyId) {
      // null → id is the initial load (companies just arrived), not a switch:
      // keep ?open=… so deep links and reloads still open the drawer.
      const wasSwitch = prevCompany.current !== null
      prevCompany.current = companyId
      if (openId && wasSwitch) closeDrawer()
    }
  }, [companyId, openId, closeDrawer])

  const onChanged = useCallback(
    (updated: StreamOut) => {
      all.setData((prev) => (prev ? prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) : prev))
    },
    [all],
  )

  if (companyId === null) return <NoCompany />

  const totalMonthly = rows.reduce((sum, s) => sum + (s.monthly_equivalent ?? 0), 0)

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Licences &amp; subscriptions</h1>
          <p>
            {all.data ? `${rows.length} of ${all.data.length} licences` : 'Every licence and subscription'}
            {rows.length > 0 && (
              <>
                {' '}
                · <span className="num">{rupees(totalMonthly)}</span> per month
              </>
            )}
          </p>
        </div>
        <div className="row">
          <button className="btn btn-sm" onClick={all.reload} disabled={all.loading}>
            Refresh
          </button>
          {canEdit && (
            <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
              + Add licence
            </button>
          )}
        </div>
      </div>

      {adding && canEdit && (
        <AddStreamForm
          companyId={companyId}
          categories={categories}
          onCancel={() => setAdding(false)}
          onCreated={(s) => {
            setAdding(false)
            all.setData((prev) => [s, ...(prev ?? [])])
          }}
        />
      )}

      <div className="filters">
        <select aria-label="Status" value={status} onChange={(e) => setParam('status', e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        <select aria-label="Category" value={category} onChange={(e) => setParam('category', e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {humanize(c)}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Search vendor, product, payee…"
          value={q}
          onChange={(e) => setParam('q', e.target.value)}
        />
        {(status || category || q) && (
          <button className="btn" onClick={() => setParams({}, { replace: true })}>
            Clear
          </button>
        )}
      </div>

      {canEdit && selected.size > 0 && (
        <div className="bulk-bar">
          <strong>{selected.size} selected</strong>
          <label className="field field-inline" style={{ marginBottom: 0 }}>
            <span>Paid on</span>
            <input type="date" value={bulkDate} onChange={(e) => setBulkDate(e.target.value)} />
          </label>
          <button className="btn btn-primary btn-sm" disabled={!!bulkBusy || !bulkDate} onClick={bulkMarkPaid}>
            {bulkBusy ? `Marking paid… ${bulkBusy.done}/${bulkBusy.total}` : `Mark ${selected.size} paid`}
          </button>
          <button className="btn btn-sm" disabled={!!bulkBusy} onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
          <span className="muted small">Uses each licence's expected amount.</span>
        </div>
      )}
      {bulkOk && <div className="msg msg-ok">{bulkOk}</div>}
      {bulkErr && <ErrorMsg>{bulkErr}</ErrorMsg>}

      {all.loading && !all.data ? (
        <Loading text="Loading licences…" />
      ) : all.error ? (
        <ErrorMsg>{all.error}</ErrorMsg>
      ) : rows.length === 0 ? (
        <div className="card">
          <Empty title={all.data && all.data.length === 0 ? 'No licences yet' : 'No matches'}>
            {all.data && all.data.length === 0
              ? 'Upload a bank statement or add a licence manually.'
              : 'Try clearing the filters.'}
          </Empty>
        </div>
      ) : (
        <div className="table-wrap cards">
          <table>
            <thead>
              <tr>
                {canEdit && (
                  <th className="col-check">
                    <input
                      type="checkbox"
                      aria-label="Select all shown"
                      checked={rows.length > 0 && rows.every((r) => selected.has(r.id))}
                      onChange={(e) =>
                        setSelected(e.target.checked ? new Set(rows.map((r) => r.id)) : new Set())
                      }
                    />
                  </th>
                )}
                <th>Vendor</th>
                <th>Product</th>
                <th>Category</th>
                <th>How often</th>
                <th className="right">Amount</th>
                <th className="right">Per month</th>
                <th>Next due</th>
                <th>Status</th>
                <th>Paid from</th>
                <th>Seen in</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr
                  key={s.id}
                  className={`clickable${selected.has(s.id) ? ' is-selected' : ''}`}
                  onClick={() => openLine(s.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') openLine(s.id)
                  }}
                >
                  {canEdit && (
                    <td className="col-check" data-label="" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Select ${s.vendor_name}`}
                        checked={selected.has(s.id)}
                        onChange={() => toggleSelected(s.id)}
                        onKeyDown={(e) => e.stopPropagation()}
                      />
                    </td>
                  )}
                  <td className="cell-primary" data-label="Vendor">
                    <strong>{s.vendor_name}</strong>
                    {s.payee_name && s.payee_name !== s.vendor_name ? (
                      <div className="cell-sub">{s.payee_name}</div>
                    ) : null}
                  </td>
                  <td data-label="Product">{s.product ?? <span className="muted">—</span>}</td>
                  <td data-label="Category">{s.category ? humanize(s.category) : <span className="muted">—</span>}</td>
                  <td data-label="How often">{CYCLE_LABEL[s.cycle] ?? s.cycle}</td>
                  <td className="right num" data-label="Amount">{rupees(s.expected_amount ?? s.avg_amount)}</td>
                  <td className="right num cell-minor" data-label="Per month">{rupees(s.monthly_equivalent)}</td>
                  <td data-label="Next due">
                    {ENDED.has(s.status) ? <span className="muted">—</span> : fmtDate(s.next_due)}
                  </td>
                  <td data-label="Status">
                    <StatusPill status={s.status} />
                  </td>
                  <td className="cell-minor" data-label="Paid from">{s.paid_from ?? <span className="muted">—</span>}</td>
                  <td className="cell-minor" data-label="Seen in">
                    <Sources sources={s.sources} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {openId && (
        <StreamDrawer
          companyId={companyId}
          streamId={parseInt(openId, 10)}
          onClose={closeDrawer}
          onChanged={onChanged}
          canEdit={canEdit}
        />
      )}
    </div>
  )
}
