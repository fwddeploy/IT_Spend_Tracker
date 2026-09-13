import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { exportUrl, getDashboard, getShareText, listQuestions } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { useDataChanged } from '../lib/events'
import { fmtDate, fmtDateTime, fmtMonth, rupees, shortMonth, humanize, sourceLabel } from '../lib/format'
import { ErrorMsg, Loading, NoCompany, StatusPill, Empty } from '../components/ui'

/** Financial year that contains today, given the month it starts in (1–12). */
function currentFY(fyStartMonth: number): number {
  const now = new Date()
  return now.getMonth() + 1 >= fyStartMonth ? now.getFullYear() : now.getFullYear() - 1
}

export default function Home() {
  const { companyId, company } = useCompany()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'fy' ? 'fy' : 'month'
  const fy = view === 'fy' ? currentFY(company?.fy_start_month ?? 4) : undefined
  const dash = useFetch(
    () => getDashboard(companyId as number, fy ? { fy } : {}),
    [companyId, fy],
    companyId !== null,
  )
  useDataChanged(dash.reload)
  const questions = useFetch(() => listQuestions(companyId as number, true), [companyId], companyId !== null)
  useDataChanged(questions.reload)
  const openQ = questions.data?.length ?? 0

  const [sharing, setSharing] = useState(false)
  const [shareErr, setShareErr] = useState<string | null>(null)
  async function share() {
    if (companyId === null) return
    setSharing(true)
    setShareErr(null)
    try {
      const { text } = await getShareText(companyId)
      window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer')
    } catch (e) {
      setShareErr(errorText(e))
    } finally {
      setSharing(false)
    }
  }

  if (companyId === null) return <NoCompany />
  if (dash.loading && !dash.data) return <Loading text="Loading…" />
  if (dash.error) return <ErrorMsg>{dash.error}</ErrorMsg>
  const d = dash.data
  if (!d) return null
  const isFY = view === 'fy' && (d.period || d.cash_out_period != null)
  const headline = isFY ? (d.cash_out_period ?? d.cash_out_month) : d.cash_out_month
  const periodLabel = isFY ? d.period ?? `FY ${fy}` : fmtMonth(d.month)
  const cb = d.cash_breakdown

  const maxCat = Math.max(1, ...d.by_category.map((c) => c.monthly_equivalent))
  const maxCal = Math.max(1, ...d.calendar.map((m) => m.cash_out))
  const avgCal = d.calendar.length
    ? d.calendar.reduce((s, m) => s + m.cash_out, 0) / d.calendar.length
    : 0

  return (
    <div className="stack home">
      <div className="page-head">
        <div>
          <h1>{company?.name}</h1>
          <p>Software and licence spend for {periodLabel}</p>
        </div>
        <div className="row">
          <div className="seg" role="group" aria-label="Period">
            <button
              className={view === 'month' ? 'on' : ''}
              onClick={() => setParams({}, { replace: true })}
            >
              Month
            </button>
            <button
              className={view === 'fy' ? 'on' : ''}
              onClick={() => setParams({ view: 'fy' }, { replace: true })}
            >
              FY
            </button>
          </div>
          <button className="btn btn-sm" onClick={share} disabled={sharing} title="Opens WhatsApp with a short summary">
            {sharing ? 'Preparing…' : 'Share on WhatsApp'}
          </button>
          <a className="btn btn-sm" href={exportUrl(companyId)} download>
            Export Excel
          </a>
          <button className="btn btn-sm" onClick={dash.reload} disabled={dash.loading}>
            Refresh
          </button>
        </div>
      </div>
      {shareErr && <ErrorMsg>{shareErr}</ErrorMsg>}

      {openQ > 0 && (
        <div className="banner home-banner">
          <span>
            <strong>{openQ}</strong> payment{openQ === 1 ? '' : 's'} need{openQ === 1 ? 's' : ''} a quick answer
          </span>
          <Link to="/attention" className="btn btn-sm btn-primary">
            Answer →
          </Link>
        </div>
      )}

      <div className="grid-2 home-numbers">
        <div className="card">
          <div className="bignum-label">{isFY ? `Going out in ${periodLabel}` : 'Going out this month'}</div>
          <div className="bignum num">{rupees(headline)}</div>
          {cb ? (
            <div className="bignum-hint breakdown">
              Paid so far <span className="num">{rupees(cb.paid)}</span> · Still due{' '}
              <span className="num">{rupees(cb.still_due)}</span>
              {cb.estimate > 0 ? (
                <>
                  {' '}· Estimate for pay-as-you-go <span className="num">{rupees(cb.estimate)}</span>
                </>
              ) : null}
            </div>
          ) : (
            <div className="bignum-hint">Actual payments due or paid in {periodLabel}.</div>
          )}
        </div>
        <div className="card">
          <div className="bignum-label">Per month</div>
          <div className="bignum num">{rupees(d.monthly_equivalent)}</div>
          <div className="bignum-hint">
            Every licence spread evenly: yearly ÷ 12, quarterly ÷ 3, and so on. Per year{' '}
            <span className="num">{rupees(d.annualised)}</span>.
          </div>
        </div>
      </div>

      <div className="grid-4 home-counters">
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
          <div className="counter-label">To check</div>
        </Link>
      </div>

      <div className="grid-2 home-dues">
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

        <div className="card home-categories">
          <div className="card-title">By category (per month)</div>
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

      <div className="card home-calendar">
        <div className="card-title">{isFY ? `Cash-out by month (${periodLabel})` : 'Cash-out by month (next 12 months)'}</div>
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
              renewals in March/April. Hover or tap a bar to see the items.
            </div>
          </>
        )}
      </div>

      <div className="card home-sync">
        <div className="card-title">Statements on file</div>
        {d.sync_health.length === 0 ? (
          <Empty title="No statements yet">
            <Link to="/upload">Upload a bank or card statement</Link> to get started.
          </Empty>
        ) : (
          d.sync_health.map((s) => (
            <div key={`${s.account_label}-${s.source_kind}`} className="sync-item">
              <div className="row">
                <strong>{s.account_label}</strong>
                <span className="tag">{sourceLabel(s.source_kind)}</span>
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
