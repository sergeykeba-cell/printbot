// src/components/FiltersBar.tsx
import { useTranslation } from 'react-i18next'
import { Search, X } from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { cn } from '@/lib/cn'
import type { JobStatus } from '@/types/printbot'

type Filter = JobStatus | 'all'

const FILTERS: Filter[] = ['all', 'draft', 'processing', 'ready_to_print', 'printed', 'failed']

const STATUS_DOT: Record<Filter, string> = {
  all: 'bg-slate-500',
  draft: 'bg-sky-500',
  processing: 'bg-amber-400 animate-pulse',
  ready_to_print: 'bg-emerald-500',
  printed: 'bg-slate-500',
  failed: 'bg-red-500',
}

export function FiltersBar() {
  const { t } = useTranslation()
  const { statusFilter, setStatusFilter, searchQuery, setSearchQuery } = useUiStore()

  return (
    <div className="flex flex-col gap-2 py-3">
      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto scrollbar-none pb-0.5" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f}
            role="tab"
            aria-selected={statusFilter === f}
            onClick={() => setStatusFilter(f)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap',
              'transition-colors min-h-[36px] focus-visible:outline-none',
              'focus-visible:ring-2 focus-visible:ring-sky-500',
              statusFilter === f
                ? 'bg-slate-700 text-white font-medium'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            )}
          >
            <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', STATUS_DOT[f])} />
            {t(`filters.${f}`)}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
        />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Пошук по ID замовлення..."
          className={cn(
            'w-full pl-8 pr-8 py-2 rounded-lg text-sm',
            'bg-slate-800/60 border border-slate-700/50',
            'text-slate-200 placeholder:text-slate-600',
            'focus:outline-none focus:ring-1 focus:ring-sky-500 focus:border-sky-500',
            'transition-colors'
          )}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1
                       text-slate-500 hover:text-slate-300 transition-colors"
            aria-label="Очистити пошук"
          >
            <X size={12} />
          </button>
        )}
      </div>
    </div>
  )
}
