import { NavLink, Outlet, Link } from 'react-router-dom'
import { useCompany } from '../lib/company'
import { useFetch } from '../lib/useFetch'
import { listQuestions } from '../lib/api'
import { useDataChanged } from '../lib/events'

export default function Layout() {
  const { companies, company, companyId, select, loading, error } = useCompany()
  const questions = useFetch(() => listQuestions(companyId as number, true), [companyId], companyId !== null)
  useDataChanged(questions.reload)
  const openCount = questions.data?.length ?? 0

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            IT Tracker
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/lines">Lines</NavLink>
            <NavLink to="/upcoming">Upcoming</NavLink>
            <NavLink to="/attention">
              Attention
              {openCount > 0 && <span className="badge">{openCount}</span>}
            </NavLink>
            <NavLink to="/upload">Upload</NavLink>
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
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
