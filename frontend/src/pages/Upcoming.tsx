import { useEffect } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { getUpcoming } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch } from '../lib/useFetch'
import { useDataChanged } from '../lib/events'
import { CYCLE_LABEL, fmtDate, fmtMonth, rupees, daysUntil } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany, StatusPill } from '../components/ui'

const WINDOWS = [90, 180, 365] as const

export default function Upcoming() {
  const { companyId } = useCompany()
  const [params, setParams] = useSearchParams()
  const daysRaw = parseInt(params.get('days') ?? '90', 10)
  const days = (WINDOWS as readonly number[]).includes(daysRaw) ? daysRaw : 90

  const up = useFetch(() => getUpcoming(companyId as number, days), [companyId, days], companyId !== null)
  useDataChanged(up.reload)

  // Dashboard calendar bars link here with #YYYY-MM; scroll to it once data is in.
  const { hash } = useLocation()
  useEffect(() => {
    if (!hash || !up.data) return
    const el = document.getElementById(hash.slice(1))
    if (el) el.scrollIntoView({ block: 'start' })
  }, [hash, up.data])

  if (companyId === null) return <NoCompany />

  const grandTotal = (up.data ?? []).reduce((s, m) => s + m.total, 0)
  const itemCount = (up.data ?? []).reduce((s, m) => s + m.items.length, 0)

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Upcoming dues</h1>
          <p>
            {up.data ? (
              <>
                {itemCount} payment{itemCount === 1 ? '' : 's'} totalling{' '}
                <span className="num">{rupees(grandTotal)}</span> in the next {days} days
              </>
            ) : (
              `Next ${days} days`
            )}
          </p>
        </div>
        <div className="seg" role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              className={w === days ? 'on' : ''}
              onClick={() => setParams({ days: String(w) }, { replace: true })}
            >
              {w} days
            </button>
          ))}
        </div>
      </div>

      {up.loading && !up.data ? (
        <Loading text="Loading upcoming dues…" />
      ) : up.error ? (
        <ErrorMsg>{up.error}</ErrorMsg>
      ) : !up.data || up.data.length === 0 ? (
        <div className="card">
          <Empty title="Nothing due">No payments fall in the next {days} days.</Empty>
        </div>
      ) : (
        up.data.map((m) => (
          <section key={m.month} id={m.month} className="month-group">
            <div className="month-head">
              <h2>{fmtMonth(m.month)}</h2>
              <div>
                <span className="muted small">{m.items.length} item{m.items.length === 1 ? '' : 's'} · </span>
                <strong className="num">{rupees(m.total)}</strong>
              </div>
            </div>
            <div className="table-wrap cards">
              <table>
                <thead>
                  <tr>
                    <th>Due</th>
                    <th>Vendor</th>
                    <th>Product</th>
                    <th>How often</th>
                    <th className="right">Amount</th>
                    <th>Status</th>
                    <th>Paid from</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {m.items.map((it) => {
                    const dl = daysUntil(it.due)
                    return (
                      <tr key={`${it.id}-${it.due}`}>
                        <td data-label="Due">
                          {fmtDate(it.due)}
                          {dl !== null && (
                            <div className="cell-sub">
                              {dl < 0 ? `${-dl}d overdue` : dl === 0 ? 'today' : `in ${dl}d`}
                            </div>
                          )}
                        </td>
                        <td data-label="Vendor">
                          <Link to={`/lines?open=${it.id}`}>
                            <strong>{it.vendor_name}</strong>
                          </Link>
                        </td>
                        <td data-label="Product">{it.product ?? <span className="muted">—</span>}</td>
                        <td className="cell-minor" data-label="How often">{CYCLE_LABEL[it.cycle] ?? it.cycle}</td>
                        <td className="right num" data-label="Amount">{rupees(it.expected_amount ?? it.avg_amount)}</td>
                        <td data-label="Status">
                          <StatusPill status={it.status} />
                        </td>
                        <td className="cell-minor" data-label="Paid from">{it.paid_from ?? <span className="muted">—</span>}</td>
                        <td data-label="">
                          {it.pay_url ? (
                            <a className="btn btn-sm" href={it.pay_url} target="_blank" rel="noopener noreferrer">
                              Pay now
                            </a>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}
    </div>
  )
}
