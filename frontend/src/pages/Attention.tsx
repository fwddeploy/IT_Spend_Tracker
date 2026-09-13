import { useState } from 'react'
import { Link } from 'react-router-dom'
import { answerQuestion, listQuestions, type Question } from '../lib/api'
import { useCompany } from '../lib/company'
import { useFetch, errorText } from '../lib/useFetch'
import { notifyDataChanged, useDataChanged } from '../lib/events'
import { fmtDate, rupees } from '../lib/format'
import { Empty, ErrorMsg, Loading, NoCompany } from '../components/ui'

const KIND_LABEL: Record<Question['kind'], string> = {
  vendor: 'Which software is this?',
  cycle: 'Billing cycle',
  split: 'Split payment',
  stopped: 'Stopped paying?',
  bundle: 'Bundle',
}

export default function Attention() {
  const { companyId } = useCompany()
  const qs = useFetch(() => listQuestions(companyId as number, true), [companyId], companyId !== null)
  useDataChanged(qs.reload)

  if (companyId === null) return <NoCompany />

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Needs attention</h1>
          <p>Quick answers that help us classify payments correctly.</p>
        </div>
        <button className="btn btn-sm" onClick={qs.reload} disabled={qs.loading}>
          Refresh
        </button>
      </div>

      {qs.loading && !qs.data ? (
        <Loading text="Loading questions…" />
      ) : qs.error ? (
        <ErrorMsg>{qs.error}</ErrorMsg>
      ) : !qs.data || qs.data.length === 0 ? (
        <div className="card">
          <Empty title="Nothing to check — all clear">
            New questions appear here after you <Link to="/upload">upload a statement</Link>.
          </Empty>
        </div>
      ) : (
        <div>
          {qs.data.map((q) => (
            <QuestionCard
              key={q.id}
              companyId={companyId}
              q={q}
              onAnswered={() => {
                qs.setData((prev) => (prev ? prev.filter((x) => x.id !== q.id) : prev))
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
  onAnswered,
}: {
  companyId: number
  q: Question
  onAnswered: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [pendingChoice, setPendingChoice] = useState<string | null>(null)

  const ctx = q.context ?? {}
  const dates = Array.isArray(ctx.dates) ? (ctx.dates as string[]) : []
  // Any other scalar context fields we don't specifically know about.
  const extra = Object.entries(ctx).filter(
    ([k, v]) => !['payee', 'amount', 'dates'].includes(k) && (typeof v === 'string' || typeof v === 'number'),
  )

  // Heuristic: an option whose key/label mentions "other"/"type"/"enter" needs free text.
  const needsText = (key: string, label: string) =>
    /other|type|enter|name it|custom|specify/i.test(key + ' ' + label)

  async function send(choice: string, freeText?: string) {
    setBusy(choice)
    setErr(null)
    try {
      await answerQuestion(companyId, q.id, freeText ? { choice, text: freeText } : { choice })
      onAnswered()
    } catch (e) {
      setErr(errorText(e))
      setBusy(null)
    }
  }

  return (
    <div className="question">
      <div className="kind">{KIND_LABEL[q.kind] ?? q.kind}</div>
      <div className="prompt">{q.prompt}</div>
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
        {extra.map(([k, v]) => (
          <span key={k}>
            {k.replace(/_/g, ' ')}: {String(v)}
          </span>
        ))}
        {q.stream_id ? <Link to={`/lines?open=${q.stream_id}`}>View line</Link> : null}
      </div>

      {pendingChoice === null ? (
        <div className="options">
          {q.options.map((o) => (
            <button
              key={o.key}
              className="btn btn-sm"
              disabled={busy !== null}
              onClick={() => (needsText(o.key, o.label) ? setPendingChoice(o.key) : send(o.key))}
            >
              {busy === o.key ? 'Saving…' : o.label}
            </button>
          ))}
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
