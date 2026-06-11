// src/components/OfflineBanner.tsx
import { WifiOff } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useUiStore } from '@/stores/uiStore'

export function OfflineBanner() {
  const { t } = useTranslation()
  const isOnline = useUiStore((s) => s.isOnline)

  if (isOnline) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="w-full bg-amber-500/10 border-b border-amber-500/20 px-4 py-2
                 flex items-center gap-2 text-amber-400 text-sm"
    >
      <WifiOff size={14} />
      <span>{t('offline.banner')}</span>
    </div>
  )
}
