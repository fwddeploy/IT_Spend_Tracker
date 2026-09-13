import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ApiError,
  UNAUTHORIZED_EVENT,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  type AuthCompany,
  type AuthResult,
  type User,
} from './api'

export type AuthStatus = 'loading' | 'authed' | 'anon'

interface AuthCtx {
  status: AuthStatus
  user: User | null
  /** Companies with the user's role in each (from /auth/me). */
  memberships: AuthCompany[]
  /** Set when /auth/me failed for a reason other than "not logged in". */
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (body: { name: string; email: string; password: string; company_name: string }) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<User | null>(null)
  const [memberships, setMemberships] = useState<AuthCompany[]>([])
  const [error, setError] = useState<string | null>(null)

  const apply = useCallback((r: AuthResult) => {
    setUser(r.user)
    setMemberships(r.companies ?? [])
    setStatus('authed')
    setError(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      apply(await getMe())
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUser(null)
        setMemberships([])
        setStatus('anon')
        setError(null)
      } else {
        // Server down etc. — treat as logged out but keep the message for the login page.
        setStatus('anon')
        setError(e instanceof Error ? e.message : 'Could not reach the server.')
      }
    }
  }, [apply])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Any 401 from a data route means the session is gone → back to /login.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null)
      setMemberships([])
      setStatus('anon')
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      apply(await apiLogin({ email, password }))
    },
    [apply],
  )

  const register = useCallback(
    async (body: { name: string; email: string; password: string; company_name: string }) => {
      apply(await apiRegister(body))
    },
    [apply],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
      setMemberships([])
      setStatus('anon')
    }
  }, [])

  const value = useMemo<AuthCtx>(
    () => ({ status, user, memberships, error, login, register, logout, refresh }),
    [status, user, memberships, error, login, register, logout, refresh],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be used inside AuthProvider')
  return v
}
