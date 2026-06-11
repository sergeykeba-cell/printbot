// src/components/JobsQueue.tsx
import { useRef, useEffect } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useTranslation } from 'react-i18next'
import { RefreshCw, AlertCircle, InboxIcon } from 'lucide-react'
import { useJobsQueue } from '@/hooks/useJobsQueue'
import { useNewJobSound } from '@/hooks/useNewJobSound'
import { useUiStore } from '@/stores/uiStore'
import { JobCard } from './JobCard'
import { JobDetailsDrawer } from './JobDetailsDrawer'


const CARD_ESTIMATE_HEIGHT = 160   // px — приблизна висота картки

export function JobsQueue() {
  const { t } = useTranslation()
  const { jobs, isLoading, isError, refetch, isFetchingNextPage, hasNextPage, fetchNextPage } =
    useJobsQueue()

  useNewJobSound()

  const { selectedJobId, setSelectedJobId } = useUiStore()
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: jobs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => CARD_ESTIMATE_HEIGHT,
    overscan: 5,
  })

  // Infinite scroll — підвантажуємо наступну сторінку
  useEffect(() => {
    const [lastItem] = [...virtualizer.getVirtualItems()].reverse()
    if (!lastItem) return
    if (lastItem.index >= jobs.length - 1 && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [virtualizer.getVirtualItems(), jobs.length, hasNextPage, isFetchingNextPage, fetchNextPage])

  // ─── Loading state ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  // ─── Error state ──────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-slate-500">
        <AlertCircle size={36} className="text-red-500/60" />
        <p className="text-sm">{t('error.load_failed')}</p>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg
                     bg-slate-800 hover:bg-slate-700 text-slate-300
                     text-sm transition-colors min-h-[44px]"
        >
          <RefreshCw size={14} />
          {t('actions.retry')}
        </button>
      </div>
    )
  }

  // ─── Empty state ──────────────────────────────────────────────────────────
  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-slate-600">
        <InboxIcon size={40} strokeWidth={1} />
        <p className="text-sm">{t('empty.queue')}</p>
      </div>
    )
  }

  // ─── Virtual list ─────────────────────────────────────────────────────────
  return (
    <>
      <div
        ref={parentRef}
        className="overflow-y-auto"
        style={{ height: 'calc(100vh - 140px)' }}
      >
        <div
          style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}
        >
          {virtualizer.getVirtualItems().map((vItem) => {
            const job = jobs[vItem.index]
            return (
              <div
                key={vItem.key}
                data-index={vItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${vItem.start}px)`,
                  paddingBottom: '12px',
                }}
              >
                <JobCard
                  job={job}
                  isSelected={selectedJobId === job.id}
                  onClick={() => setSelectedJobId(job.id)}
                />
              </div>
            )
          })}
        </div>

        {isFetchingNextPage && (
          <div className="flex justify-center py-4">
            <RefreshCw size={16} className="animate-spin text-slate-600" />
          </div>
        )}
      </div>

      {/* Drawer відкривається при selectedJobId */}
      {selectedJobId && (
        <JobDetailsDrawer
          jobId={selectedJobId}
          onClose={() => setSelectedJobId(null)}
        />
      )}
    </>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-3.5 animate-pulse">
      <div className="flex justify-between mb-3">
        <div className="h-3 w-20 bg-slate-800 rounded" />
        <div className="h-5 w-24 bg-slate-800 rounded-full" />
      </div>
      <div className="h-3 w-32 bg-slate-800 rounded mb-3" />
      <div className="space-y-1.5 mb-3">
        <div className="h-3 w-full bg-slate-800 rounded" />
        <div className="h-3 w-3/4 bg-slate-800 rounded" />
      </div>
      <div className="flex gap-1.5">
        {[40, 32, 28].map((w) => (
          <div key={w} className="h-5 bg-slate-800 rounded" style={{ width: w }} />
        ))}
      </div>
    </div>
  )
}
