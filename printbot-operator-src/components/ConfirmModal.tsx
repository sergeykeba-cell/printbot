// src/components/ConfirmModal.tsx
import { useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/cn'

interface Props {
  title: string
  body: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  danger?: boolean
}

export function ConfirmModal({ title, body, confirmLabel, onConfirm, onCancel, danger }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    cancelRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        style={{ zIndex: 200 }}
        onClick={onCancel}
        aria-hidden="true"
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        aria-describedby="modal-body"
        className={cn(
          'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2',
          'w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl p-6',
          'shadow-2xl'
        )}
        style={{ zIndex: 201 }}
      >
        {danger && (
          <div className="flex justify-center mb-4">
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
              <AlertTriangle size={22} className="text-red-400" />
            </div>
          </div>
        )}

        <h3 id="modal-title" className="text-base font-semibold text-white text-center mb-2">
          {title}
        </h3>
        <p id="modal-body" className="text-sm text-slate-400 text-center mb-6">
          {body}
        </p>

        <div className="flex gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            className={cn(
              'flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors min-h-[44px]',
              'bg-slate-800 hover:bg-slate-700 text-slate-300',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500'
            )}
          >
            Скасувати
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              'flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors min-h-[44px]',
              danger
                ? 'bg-red-600 hover:bg-red-500 text-white'
                : 'bg-sky-600 hover:bg-sky-500 text-white',
              'focus-visible:outline-none focus-visible:ring-2',
              danger ? 'focus-visible:ring-red-500' : 'focus-visible:ring-sky-500'
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </>
  )
}
