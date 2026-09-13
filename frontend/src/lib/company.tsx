import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { listCompanies, type Company } from './api'
import { errorText } from './useFetch'

const LS_KEY = 'it-tracker.company_id'

function readStored(): number | null {
  try {
    const v = localStorage.getItem(LS_KEY)
    if (!v) return null
    const n = parseInt(v, 10)
    return Number.isFinite(n) ? n : null
  } catch {
    return null
  }
}

function writeStored(id: number | null) {
  try {
    if (id === null) localStorage.removeItem(LS_KEY)
    else localStorage.setItem(LS_KEY, String(id))
  } catch {
    /* storage unavailable (private mode etc.) */
  }
}

interface CompanyCtx {
  companies: Company[]
  loading: boolean
  error: string | null
  company: Company | null
  companyId: number | null
  select: (id: number) => void
  reload: () => Promise<void>
  /** Add a freshly created company to the list and select it. */
  add: (c: Company) => void
}

const Ctx = createContext<CompanyCtx | null>(null)

export function CompanyProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [companyId, setCompanyId] = useState<number | null>(readStored)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await listCompanies()
      setCompanies(list)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  // Default to first company if nothing stored or stored id no longer exists.
  useEffect(() => {
    if (companies.length === 0) return
    if (companyId === null || !companies.some((c) => c.id === companyId)) {
      setCompanyId(companies[0].id)
      writeStored(companies[0].id)
    }
  }, [companies, companyId])

  const select = useCallback((id: number) => {
    setCompanyId(id)
    writeStored(id)
  }, [])

  const add = useCallback((c: Company) => {
    setCompanies((prev) => [...prev, c])
    setCompanyId(c.id)
    writeStored(c.id)
  }, [])

  const company = useMemo(
    () => companies.find((c) => c.id === companyId) ?? null,
    [companies, companyId],
  )

  const value = useMemo<CompanyCtx>(
    () => ({
      companies,
      loading,
      error,
      company,
      companyId: company ? company.id : null,
      select,
      reload,
      add,
    }),
    [companies, loading, error, company, select, reload, add],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useCompany(): CompanyCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useCompany must be used inside CompanyProvider')
  return v
}
