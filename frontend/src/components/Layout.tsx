import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom'
import { useCompany } from '../lib/company'
import { useAuth } from '../lib/auth'
import { useFetch } from '../lib/useFetch'
import { getSettings, listQuestions } from '../lib/api'
import { useDataChanged } from '../lib/events'

export function isSampleCompany(name: string | null | undefined): boolean {
  return /\(sample\)/i.test(name ?? '')
}

export default function Layout() {
  const { companies, company, companyId, select, loading, error } = useCompany()
  const auth = useAuth()
  const navigate = useNavigate()
  const questions = useFetch(() => listQuestions(companyId as number, true), [companyId], companyId !== null)
  useDataChanged(questions.reload)
  const openCount = questions.data?.length ?? 0

  // Short company name for the top bar lives in settings (v2). Silently ignore
  // failures — a v1 backend has no settings route.
  const settings = useFetch(() => getSettings(companyId as number), [companyId], companyId !== null)
  useDataChanged(settings.reload)
  const shortName = settings.data?.short_name?.trim() || company?.short_name?.trim() || ''

  async function doLogout() {
    await auth.logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            IT Tracker
            {shortName && <span className="brand-company"> · {shortName}</span>}
            {isSampleCompany(company?.name) && <span className="pill pill-amber sample-badge">Sample data</span>}
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/lines">Licences</NavLink>
            <NavLink to="/upcoming">Upcoming</NavLink>
            <NavLink to="/attention">
              Attention
              {openCount > 0 && <span className="badge">{openCount}</span>}
            </NavLink>
            <NavLink to="/upload">Upload</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </nav>
          <div className="topbar-right">
            {loading ? (
              <span className="muted small">Loading companies…</span>
            ) : error ? (
              <span className="small" style={{ color: 'var(--danger)' }} title={error}>
                Companies unavailable
              </span>
            ) : companies.length === 0 ? (
              <Link to="/upload" className="small">
                Create a company
              </Link>
            ) : (
              <select
                aria-label="Company"
                value={company?.id ?? ''}
                onChange={(e) => select(parseInt(e.target.value, 10))}
                style={{ width: 'auto', maxWidth: 220 }}
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
            {auth.user && (
              <span className="user-chip">
                <span className="user-name" title={auth.user.email}>
                  {auth.user.name || auth.user.email}
                </span>
                <button type="button" className="btn btn-sm" onClick={doLogout}>
                  Logout
                </button>
              </span>
            )}
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
