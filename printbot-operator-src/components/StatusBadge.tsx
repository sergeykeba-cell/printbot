// src/components/StatusBadge.tsx
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/cn'
import type { JobStatus } from '@/types/printbot'

interface Props {
  status: JobStatus
  size?: 'sm' | 'md'
}

const STYLES: Record<JobStatus, string> = {
  draft:          'bg-sky-500/10 text-sky-400 border-sky-500/20',
  processing:     'bg-amber-500/10 text-amber-400 border-amber-500/20',
  ready_to_print: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  printed:        'bg-slate-500/10 text-slate-400 border-slate-500/20',
  failed:         'bg-red-500/10 text-red-400 border-red-500/20',
}

export function StatusBadge({ status, size = 'sm' }: Props) {
  const { t } = useTranslation()

  return (
    <span
      aria-label={`Статус: ${t(`status.${status}`)}`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
        STYLES[status]
      )}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full flex-shrink-0',
          status === 'processing' && 'animate-pulse-slow',
          status === 'draft'          && 'bg-sky-400',
          status === 'processing'     && 'bg-amber-400',
          status === 'ready_to_print' && 'bg-emerald-400',
          status === 'printed'        && 'bg-slate-400',
          status === 'failed'         && 'bg-red-400',
        )}
      />
      {t(`status.${status}`)}
    </span>
  )
}
