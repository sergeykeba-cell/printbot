// src/components/ToastContainer.tsx
import { useState, useEffect } from 'react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { ToastPayload } from '@/lib/toast'

const ICONS = {
  success: <CheckCircle2 size={15} className="text-emerald-400 flex-shrink-0" />,
  error:   <AlertCircle  size={15} className="text-red-400 flex-shrink-0" />,
  info:    <Info         size={15} className="text-sky-400 flex-shrink-0" />,
}

const BORDER = {
  success: 'border-emerald-500/20',
  error:   'border-red-500/20',
  info:    'border-sky-500/20',
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastPayload[]>([])

  useEffect(() => {
    const handler = (e: Event) => {
      const toast = (e as CustomEvent<ToastPayload>).detail
      setToasts((prev) => [...prev, toast])
      // Авто-видалення через 4 секунди
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, 4_000)
    }
    window.addEventListener('printbot:toast', handler)
    return () => window.removeEventListener('printbot:toast', handler)
  }, [])

  if (toasts.length === 0) return null

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-4 right-4 z-80 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-center gap-2.5 px-3.5 py-3 rounded-xl',
            'bg-slate-900 border shadow-lg',
            'text-sm text-slate-200',
            'pointer-events-auto',
            'animate-in slide-in-from-bottom-2 fade-in duration-200',
            BORDER[t.type]
          )}
        >
          {ICONS[t.type]}
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="text-slate-600 hover:text-slate-400 transition-colors"
            aria-label="Закрити"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  )
}
