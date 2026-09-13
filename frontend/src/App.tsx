import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/auth'
import { CompanyProvider } from './lib/company'
import Layout from './components/Layout'
import Home from './pages/Home'
import Lines from './pages/Lines'
import Upcoming from './pages/Upcoming'
import Attention from './pages/Attention'
import Upload from './pages/Upload'
import Settings from './pages/Settings'
import Login from './pages/Login'
import Register from './pages/Register'
import { Loading } from './components/ui'

/** Everything inside needs a logged-in user; otherwise go to /login and come back after. */
function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <div className="page"><Loading text="Checking your login…" /></div>
  if (status === 'anon') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/** Login/register pages bounce to the app when already logged in. */
function AnonOnly() {
  const { status } = useAuth()
  if (status === 'loading') return <div className="page"><Loading text="Checking your login…" /></div>
  if (status === 'authed') return <Navigate to="/" replace />
  return <Outlet />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CompanyProvider>
          <Routes>
            <Route element={<AnonOnly />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Route>
            <Route element={<RequireAuth />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Home />} />
                <Route path="/lines" element={<Lines />} />
                <Route path="/upcoming" element={<Upcoming />} />
                <Route path="/attention" element={<Attention />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Route>
          </Routes>
        </CompanyProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
