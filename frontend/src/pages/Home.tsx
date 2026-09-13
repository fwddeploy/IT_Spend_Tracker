import { Link } from 'react-router-dom'
import { getDashboard } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch } from '../lib/useFetch'
import { useDataChanged } from '../lib/events'
import { fmtDate, fmtDateTime, fmtMonth, rupees, shortMonth, humanize } from '../lib/format'
import { ErrorMsg, Loading, NoCompany, StatusPill, Empty } from '../components/ui'

export default function Home() {
  const { companyId, company } = useCompany()
  const dash = useFetch(() => getDashboard(companyId as number), [companyId], companyId !== null)
  useDataChanged(dash.reload)

  if (companyId === null) return <NoCompany />
  if (dash.loading && !dash.data) return <Loading text="Loading dashboard…" />
  if (dash.error) return <ErrorMsg>{dash.error}</ErrorMsg>
  const d = dash.data
  if (!d) return null

  const maxCat = Math.max(1, ...d.by_category.map((c) => c.monthly_equivalent))
  const maxCal = Math.max(1, ...d.calendar.map((m) => m.cash_out))
  const avgCal = d.calendar.length
    ? d.calendar.reduce((s, m) => s + m.cash_out, 0) / d.calendar.length
    : 0

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>{company?.name}</h1>
          <p>Software and licence spend for {fmtMonth(d.month)}</p>
        </div>
        <button className="btn btn-sm" onClick={dash.reload} disabled={dash.loading}>
          Refresh
        </button>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="bignum-label">Going out this month</div>
          <div className="bignum num">{rupees(d.cash_out_month)}</div>
          <div className="bignum-hint">
            Actual payments due or paid in {fmtMonth(d.month)}.
          </div>
        </div>
        <div className="card">
          <div className="bignum-label">Monthly-equivalent</div>
          <div className="bignum num">{rupees(d.monthly_equivalent)}</div>
          <div className="bignum-hint">
            Every licence spread evenly: yearly ÷ 12, quarterly ÷ 3, and so on. Annualised{' '}
            <span className="num">{rupees(d.annualised)}</span>.
          </div>
        </div>
      </div>

      <div className="grid-4">
        <Link to="/lines?status=active" className="counter">
          <div className="counter-value num">{d.active_count}</div>
          <div className="counter-label">Active licences</div>
        </Link>
        <Link to="/lines?status=due_soon" className="counter is-warn">
          <div className="counter-value num">{d.due_soon_count}</div>
          <div className="counter-label">Due in 7 days</div>
        </Link>
        <Link to="/lines?status=overdue" className="counter is-danger">
          <div className="counter-value num">{d.overdue_count}</div>
          <div className="counter-label">Overdue</div>
        </Link>
        <Link to="/attention" className="counter is-info">
          <div className="counter-value num">{d.needs_confirm_count}</div>
          <div className="counter-label">Needs confirm</div>
        </Link>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title">Next 5 dues</div>
          {d.next_dues.length === 0 ? (
            <Empty title="Nothing due">No upcoming payments found.</Empty>
          ) : (
            <ul className="list">
              {d.next_dues.map((s) => (
                <li key={s.id}>
                  <div style={{ minWidth: 0 }}>
                    <div className="primary">
                      <Link to={`/lines?open=${s.id}`}>{s.vendor_name}</Link>
                      {s.product ? <span className="muted"> · {s.product}</span> : null}
                    </div>
                    <div className="secondary">
                      {fmtDate(s.next_due)} · <StatusPill status={s.status} />
                    </div>
                  </div>
                  <div className="num" style={{ fontWeight: 600 }}>
                    {rupees(s.expected_amount ?? s.avg_amount)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <div className="card-title">By category (monthly-equivalent)</div>
          {d.by_category.length === 0 ? (
            <Empty title="No categories yet" />
          ) : (
            d.by_category.map((c) => (
              <Link
                key={c.category ?? 'uncategorised'}
                to={`/lines?category=${encodeURIComponent(c.category ?? '')}`}
                className="bar-row"
                style={{ color: 'inherit' }}
              >
                <span className="bar-label" title={c.category ?? 'Uncategorised'}>
                  {humanize(c.category) === '—' ? 'Uncategorised' : humanize(c.category)}
                  <span className="muted"> ({c.count})</span>
                </span>
                <span className="bar-track">
                  <span
                    className="bar-fill"
                    style={{ width: `${Math.max(2, (c.monthly_equivalent / maxCat) * 100)}%` }}
                  />
                </span>
                <span className="bar-val num">{rupees(c.monthly_equivalent)}</span>
              </Link>
            ))
          )}
          <div className="bignum-hint" style={{ marginTop: 10 }}>
            Auto-renew {rupees(d.committed_vs_manual.auto_renew)} · Manual{' '}
            {rupees(d.committed_vs_manual.manual)} per month.
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Cash-out by month (next 12 months)</div>
        {d.calendar.length === 0 ? (
          <Empty title="No calendar data" />
        ) : (
          <>
            <div className="calendar">
              {d.calendar.map((m) => {
                const isSpike = avgCal > 0 && m.cash_out > avgCal * 1.75
                const isCurrent = m.month === d.month
                const title =
                  `${fmtMonth(m.month)}: ${rupees(m.cash_out)}` +
                  (m.items.length
                    ? '\n' +
                      m.items
                        .map((i) => `${i.vendor_name}${i.product ? ' ' + i.product : ''} ${rupees(i.amount)} (${fmtDate(i.due)})`)
                        .join('\n')
                    : '')
                return (
                  <Link
                    key={m.month}
                    to={`/upcoming?days=365#${m.month}`}
                    className={`cal-col${isCurrent ? ' is-current' : ''}${isSpike ? ' is-spike' : ''}`}
                    title={title}
                    style={{ color: 'inherit' }}
                  >
                    <span className="cal-val num">{compactRupees(m.cash_out)}</span>
                    <span
                      className="cal-bar"
                      style={{ height: `${Math.max(2, (m.cash_out / maxCal) * 100)}%` }}
                    />
                    <span className="cal-month">{shortMonth(m.month)}</span>
                  </Link>
                )
              })}
            </div>
            <div className="cal-legend">
              Amber bars are well above the 12-month average — typically financial-year-end
              renewals in March/April. Hover a bar for the items.
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title">Sync health</div>
        {d.sync_health.length === 0 ? (
          <Empty title="No data sources yet">
            <Link to="/upload">Upload a bank or card statement</Link> to get started.
          </Empty>
        ) : (
          d.sync_health.map((s) => (
            <div key={`${s.account_label}-${s.source_kind}`} className="sync-item">
              <div className="row">
                <strong>{s.account_label}</strong>
                <span className="tag">{s.source_kind}</span>
                {s.stale && <span className="pill pill-amber">Stale — upload a newer statement</span>}
              </div>
              <div className="secondary">
                Last data {fmtDate(s.last_data_date)}, uploaded {fmtDateTime(s.last_import_at)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function compactRupees(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toLocaleString('en-IN', { maximumFractionDigits: 1 })}Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toLocaleString('en-IN', { maximumFractionDigits: 1 })}L`
  if (n >= 1e3) return `₹${(n / 1e3).toLocaleString('en-IN', { maximumFractionDigits: 0 })}k`
  return rupees(n)
}
