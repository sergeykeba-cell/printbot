// src/components/ShortcutOverlay.tsx
import { useEffect, useRef } from 'react'
import { X, Keyboard } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface Props {
  onClose: () => void
}

const SHORTCUTS = [
  { keys: ['↑', '↓'],  labelKey: 'shortcuts.navigate' },
  { keys: ['Enter'],   labelKey: 'shortcuts.open' },
  { keys: ['P'],       labelKey: 'shortcuts.printed' },
  { keys: ['F'],       labelKey: 'shortcuts.failed' },
  { keys: ['Esc'],     labelKey: 'shortcuts.close' },
  { keys: ['R'],       labelKey: 'shortcuts.refresh' },
  { keys: ['?'],       labelKey: 'shortcuts.help' },
]

export function ShortcutOverlay({ onClose }: Props) {
  const { t } = useTranslation()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <div
        className="fixed inset-0 z-60 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        className="fixed z-70 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
                   w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl"
      >
        <div className="flex items-center gap-2 mb-5">
          <Keyboard size={16} className="text-slate-400" />
          <h2 id="shortcuts-title" className="text-sm font-semibold text-white flex-1">
            {t('shortcuts.title')}
          </h2>
          <button
            ref={closeRef}
            onClick={onClose}
            className="p-1 rounded-lg text-slate-500 hover:text-slate-300
                       hover:bg-slate-800 transition-colors"
            aria-label="Закрити"
          >
            <X size={14} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {SHORTCUTS.map(({ keys, labelKey }) => (
            <div key={labelKey} className="flex items-center justify-between gap-3">
              <span className="text-xs text-slate-400">{t(labelKey)}</span>
              <div className="flex gap-1 flex-shrink-0">
                {keys.map((k) => (
                  <kbd
                    key={k}
                    className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700
                               text-xs font-mono text-slate-300 min-w-[24px] text-center"
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
