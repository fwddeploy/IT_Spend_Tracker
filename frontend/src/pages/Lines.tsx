import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listStreams, STATUSES, type StreamOut } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch } from '../lib/useFetch'
import { useDataChanged } from '../lib/events'
import { CYCLE_LABEL, STATUS_LABEL, fmtDate, rupees, humanize } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany, Sources, StatusPill } from '../components/ui'
import StreamDrawer from '../components/StreamDrawer'
import AddStreamForm from '../components/AddStreamForm'

// Lines that no longer recur: a "next due" date is stale and misleading.
const ENDED = new Set(['cancelled', 'stopped', 'dismissed', 'one_time'])

export default function Lines() {
  const { companyId } = useCompany()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? ''
  const category = params.get('category') ?? ''
  const q = params.get('q') ?? ''
  const openId = params.get('open')
  const [adding, setAdding] = useState(false)

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

  const closeDrawer = useCallback(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('open')
        return next
      },
      { replace: true },
    )
  }, [setParams])

  // Switching company while a line is open would leave a dead "not found"
  // drawer (the id belongs to the other company) — close it instead.
  const prevCompany = useRef(companyId)
  useEffect(() => {
    if (prevCompany.current !== companyId) {
      prevCompany.current = companyId
      if (openId) closeDrawer()
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
          <h1>Line items</h1>
          <p>
            {all.data ? `${rows.length} of ${all.data.length} licences` : 'Every licence and subscription'}
            {rows.length > 0 && (
              <>
                {' '}
                · <span className="num">{rupees(totalMonthly)}</span>/month equivalent
              </>
            )}
          </p>
        </div>
        <div className="row">
          <button className="btn btn-sm" onClick={all.reload} disabled={all.loading}>
            Refresh
          </button>
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            + Add licence
          </button>
        </div>
      </div>

      {adding && (
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
                <th>Vendor</th>
                <th>Product</th>
                <th>Category</th>
                <th>Cycle</th>
                <th className="right">Amount</th>
                <th className="right">Monthly-eq.</th>
                <th>Next due</th>
                <th>Status</th>
                <th>Paid from</th>
                <th>Sources</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr
                  key={s.id}
                  className="clickable"
                  onClick={() => setParam('open', String(s.id))}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setParam('open', String(s.id))
                  }}
                >
                  <td className="cell-primary" data-label="Vendor">
                    <strong>{s.vendor_name}</strong>
                    {s.payee_name && s.payee_name !== s.vendor_name ? (
                      <div className="cell-sub">{s.payee_name}</div>
                    ) : null}
                  </td>
                  <td data-label="Product">{s.product ?? <span className="muted">—</span>}</td>
                  <td data-label="Category">{s.category ? humanize(s.category) : <span className="muted">—</span>}</td>
                  <td data-label="Cycle">{CYCLE_LABEL[s.cycle] ?? s.cycle}</td>
                  <td className="right num" data-label="Amount">{rupees(s.expected_amount ?? s.avg_amount)}</td>
                  <td className="right num cell-minor" data-label="Monthly-eq.">{rupees(s.monthly_equivalent)}</td>
                  <td data-label="Next due">
                    {ENDED.has(s.status) ? <span className="muted">—</span> : fmtDate(s.next_due)}
                  </td>
                  <td data-label="Status">
                    <StatusPill status={s.status} />
                  </td>
                  <td className="cell-minor" data-label="Paid from">{s.paid_from ?? <span className="muted">—</span>}</td>
                  <td className="cell-minor" data-label="Sources">
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
        />
      )}
    </div>
  )
}
