import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { errorText } from '../lib/useFetch'
import { ErrorMsg } from '../components/ui'

export default function Login() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from || '/'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!email.trim() || !password) return setErr('Enter your email and password.')
    setBusy(true)
    try {
      await auth.login(email.trim(), password)
      navigate(from, { replace: true })
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
        <h1 style={{ marginBottom: 4 }}>Log in</h1>
        <p className="muted" style={{ margin: '0 0 14px' }}>
          Keep track of every software licence and subscription your company pays for.
        </p>
        {auth.error && (
          <div style={{ marginBottom: 10 }}>
            <ErrorMsg>{auth.error}</ErrorMsg>
          </div>
        )}
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            required
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
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
            {busy ? 'Logging in…' : 'Log in'}
          </button>
        </div>
        <p className="small" style={{ marginTop: 16, marginBottom: 0 }}>
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  )
}
