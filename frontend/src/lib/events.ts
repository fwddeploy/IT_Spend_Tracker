import { useEffect } from 'react'

// Tiny in-app signal so unrelated components (e.g. the nav badge) can refresh
// after data changes (question answered, upload finished, engine re-run).
const NAME = 'it-tracker:data-changed'

export function notifyDataChanged() {
  window.dispatchEvent(new Event(NAME))
}

export function useDataChanged(handler: () => void) {
  useEffect(() => {
    window.addEventListener(NAME, handler)
    return () => window.removeEventListener(NAME, handler)
  }, [handler])
}
