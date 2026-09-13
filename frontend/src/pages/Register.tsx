import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { errorText } from '../lib/useFetch'
import { ErrorMsg } from '../components/ui'

export default function Register() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [f, setF] = useState({ name: '', email: '', password: '', company_name: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!f.name.trim()) return setErr('Your name is required.')
    if (!f.email.trim()) return setErr('Email is required.')
    if (f.password.length < 8) return setErr('Use a password of at least 8 characters.')
    if (!f.company_name.trim()) return setErr('Company name is required.')
    setBusy(true)
    try {
      await auth.register({
        name: f.name.trim(),
        email: f.email.trim(),
        password: f.password,
        company_name: f.company_name.trim(),
      })
      navigate('/upload', { replace: true })
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <div className="brand" style={{ marginBottom: 4 }}>IT Tracker</div>
        <h1 style={{ marginBottom: 4 }}>Create an account</h1>
        <p className="muted" style={{ margin: '0 0 14px' }}>
          You become the owner of your company. You can invite your accountant later from Settings.
        </p>
        <label className="field">
          <span>Your name</span>
          <input
            type="text"
            value={f.name}
            onChange={(e) => setF({ ...f, name: e.target.value })}
            autoComplete="name"
            autoFocus
            required
          />
        </label>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={f.email}
            onChange={(e) => setF({ ...f, email: e.target.value })}
            autoComplete="email"
            required
          />
        </label>
        <label className="field">
          <span>Password (8+ characters)</span>
          <input
            type="password"
            value={f.password}
            onChange={(e) => setF({ ...f, password: e.target.value })}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <label className="field">
          <span>Company name</span>
          <input
            type="text"
            value={f.company_name}
            onChange={(e) => setF({ ...f, company_name: e.target.value })}
            placeholder="e.g. Sharma Auto Components Pvt Ltd"
            required
          />
        </label>
        {err && (
          <div style={{ marginBottom: 10 }}>
            <ErrorMsg>{err}</ErrorMsg>
          </div>
        )}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </div>
        <p className="small" style={{ marginTop: 16, marginBottom: 0 }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
