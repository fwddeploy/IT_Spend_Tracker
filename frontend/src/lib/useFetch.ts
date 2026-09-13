import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

export interface FetchState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
  setData: (updater: T | ((prev: T | null) => T | null)) => void
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return 'Something went wrong.'
}

/**
 * Minimal data-fetching hook. `fn` is re-run whenever `deps` change.
 * Pass `enabled=false` to skip (e.g. no company selected yet).
 */
export function useFetch<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  enabled = true,
): FetchState<T> {
  const [data, setDataRaw] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const seq = useRef(0)

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    const mySeq = ++seq.current
    setLoading(true)
    setError(null)
    fn().then(
      (d) => {
        if (mySeq !== seq.current) return
        setDataRaw(d)
        setLoading(false)
      },
      (e) => {
        if (mySeq !== seq.current) return
        setError(errorText(e))
        setLoading(false)
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  const setData = useCallback((u: T | ((prev: T | null) => T | null)) => {
    setDataRaw((prev) => (typeof u === 'function' ? (u as (p: T | null) => T | null)(prev) : u))
  }, [])

  return { data, loading, error, reload, setData }
}
