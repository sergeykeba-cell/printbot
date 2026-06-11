// src/components/JobDetailsDrawer.tsx
import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  X, Download, FileText, Image, File,
  CheckCircle2, Trash2, Loader2, ExternalLink,
} from 'lucide-react'
import { getJob, patchJobStatus, deleteJob, getFileUrl, auditJobAction } from '@/api/jobs'
import { StatusBadge } from './StatusBadge'
import { ConfirmModal } from './ConfirmModal'
import { cn } from '@/lib/cn'
import { formatFull } from '@/lib/dateFormat'
import type { PrintedFile, JobStatus } from '@/types/printbot'

interface Props {
  jobId: string
  onClose: () => void
}

export function JobDetailsDrawer({ jobId, onClose }: Props) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showCancelModal, setShowCancelModal] = useState(false)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const isSubmittingRef = useRef(false)

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId),
    staleTime: 5_000,
  })

  // Trap focus + Esc
  useEffect(() => {
    closeButtonRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  // ─── Mutation: зміна статусу ──────────────────────────────────────────────
  const statusMutation = useMutation({
    mutationFn: (status: JobStatus) => patchJobStatus(jobId, status),
    onMutate: async (newStatus) => {
      if (isSubmittingRef.current) return
      isSubmittingRef.current = true
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['job', jobId] })
      const prev = queryClient.getQueryData(['job', jobId])
      queryClient.setQueryData(['job', jobId], (old: typeof job) =>
        old ? { ...old, status: newStatus } : old
      )
      // Оновлюємо і в списку
      queryClient.setQueriesData({ queryKey: ['jobs'] }, (old: unknown) => {
        const data = old as { pages: { items: { id: string; status: JobStatus }[] }[] } | undefined
        if (!data) return data
        return {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((j) =>
              j.id === jobId ? { ...j, status: newStatus } : j
            ),
          })),
        }
      })
      return { prev }
    },
    onSuccess: (_, newStatus) => {
      auditJobAction(jobId, { action: 'status_changed', new_status: newStatus })
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(['job', jobId], ctx.prev)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onSettled: () => { isSubmittingRef.current = false },
  })

  // ─── Mutation: видалення ──────────────────────────────────────────────────
  const deleteMutation = useMutation({
    mutationFn: () => deleteJob(jobId),
    onSuccess: () => {
      auditJobAction(jobId, { action: 'job_deleted' })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      onClose()
    },
  })

  const handleDownload = (file: PrintedFile) => {
    const url = getFileUrl(jobId, file.id)
    const a = document.createElement('a')
    a.href = url
    a.download = file.original_name
    a.click()
    auditJobAction(jobId, { action: 'file_download' })
  }

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className={cn(
          'fixed right-0 top-0 bottom-0 z-50 w-full max-w-[480px]',
          'bg-slate-900 border-l border-slate-800',
          'flex flex-col overflow-hidden',
          'animate-in slide-in-from-right duration-200'
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-800 flex-shrink-0">
          <h2 id="drawer-title" className="font-semibold text-white flex-1 min-w-0">
            {isLoading || !job ? (
              <span className="block h-5 w-40 bg-slate-800 rounded animate-pulse" />
            ) : (
              <span className="font-mono text-sm tracking-wider text-slate-300">
                #{job?.id.slice(0, 8).toUpperCase()}
              </span>
            )}
          </h2>
          {job && <StatusBadge status={job.status} size="md" />}
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white
                       hover:bg-slate-800 transition-colors min-h-[36px] min-w-[36px]
                       flex items-center justify-center"
            aria-label={t('actions.back')}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {isLoading || !job ? (
            <DrawerSkeleton />
          ) : job ? (
            <>
              {/* Meta */}
              <Section title={t('drawer.details')}>
                <Row label={t('job.id')}>
                  <span className="font-mono text-xs text-slate-300 break-all">{job.id}</span>
                </Row>
                <Row label={t('job.user')}>
                  <span className="font-mono text-sm text-slate-300">{job.user_id}</span>
                </Row>
                <Row label={t('job.created')}>
                  <span className="text-sm text-slate-300">{formatFull(job.created_at)}</span>
                </Row>
                <Row label={t('drawer.updated')}>
                  <span className="text-sm text-slate-300">{formatFull(job.updated_at)}</span>
                </Row>
              </Section>

              {/* Print config */}
              <Section title={t('drawer.print_config')}>
                <Row label={t('drawer.mode')}>
                  <span className="text-sm text-slate-300">
                    {job.color_mode === 'color' ? t('job.color') : t('job.bw')}
                  </span>
                </Row>
                <Row label={t('drawer.duplex')}>
                  <span className="text-sm text-slate-300">
                    {job.duplex === 'one_sided'
                      ? t('job.duplex_one_full')
                      : job.duplex === 'two_sided_long'
                      ? t('job.duplex_long_full')
                      : t('job.duplex_short_full')}
                  </span>
                </Row>
                <Row label={t('drawer.copies')}>
                  <span className="text-sm text-slate-300">{job.copies}</span>
                </Row>
                {job.files[0]?.paper_format && (
                  <Row label={t('drawer.photo_size')}>
                    <span className="text-sm text-slate-300">{job.files[0]?.paper_format}</span>
                  </Row>
                )}
              </Section>

              {/* Files */}
              <Section title={`${t('job.files')} (${job.files.length})`}>
                {job.files.length === 0 ? (
                  <p className="text-sm text-slate-600">{t('job.no_files')}</p>
                ) : (
                  <div className="space-y-3">
                    {job.files.map((f) => (
                      <FileRow key={f.id} file={f} onDownload={() => handleDownload(f)} />
                    ))}
                  </div>
                )}
              </Section>
            </>
          ) : null}
        </div>

        {/* Actions footer */}
        {job && (
          <div className="flex-shrink-0 px-5 py-4 border-t border-slate-800 flex gap-3">
            {/* Надруковано */}
            {job.status !== 'printed' && job.status !== 'failed' && (
              <button
                onClick={() => statusMutation.mutate('printed')}
                disabled={statusMutation.isPending}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2',
                  'py-2.5 rounded-xl text-sm font-medium transition-all min-h-[44px]',
                  'bg-emerald-600 hover:bg-emerald-500 text-white',
                  'disabled:opacity-60 disabled:cursor-not-allowed',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500'
                )}
              >
                {statusMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <CheckCircle2 size={16} />
                )}
                {t('actions.mark_printed')}
              </button>
            )}

            {/* Скасувати */}
            <button
              onClick={() => setShowCancelModal(true)}
              disabled={deleteMutation.isPending}
              className={cn(
                'flex items-center justify-center gap-2 px-4',
                'py-2.5 rounded-xl text-sm font-medium transition-all min-h-[44px]',
                'bg-slate-800 hover:bg-red-950 text-slate-400 hover:text-red-400',
                'border border-slate-700 hover:border-red-900',
                'disabled:opacity-60 disabled:cursor-not-allowed',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500'
              )}
            >
              {deleteMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Trash2 size={16} />
              )}
              {t('actions.cancel_job')}
            </button>
          </div>
        )}
      </aside>

      {/* Confirm modal */}
      {showCancelModal && (
        <ConfirmModal
          title={t('actions.cancel_confirm_title')}
          body={t('actions.cancel_confirm_body')}
          confirmLabel={t('actions.confirm')}
          onConfirm={() => { setShowCancelModal(false); deleteMutation.mutate() }}
          onCancel={() => setShowCancelModal(false)}
          danger
        />
      )}
    </>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
        {title}
      </h3>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-sm text-slate-500 flex-shrink-0">{label}</span>
      <div className="text-right min-w-0">{children}</div>
    </div>
  )
}

function FileRow({ file, onDownload }: { file: PrintedFile; onDownload: () => void }) {
  const { t } = useTranslation()
  const isImage = file.mime_type.startsWith('image/')
  const isPdf   = file.mime_type === 'application/pdf'

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-800/40 p-3">
      <div className="flex items-start gap-2 mb-2">
        <div className="mt-0.5 flex-shrink-0">
          {isImage ? (
            <Image size={14} className="text-sky-400" />
          ) : isPdf ? (
            <FileText size={14} className="text-red-400" />
          ) : (
            <File size={14} className="text-slate-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-300 truncate">{file.original_name}</p>
          <div className="flex gap-2 mt-0.5 flex-wrap">
            {file.page_count != null && (
              <span className="text-xs text-slate-600">{file.page_count} {t('job.pages')}</span>
            )}
            {file.paper_format && (
              <span className="text-xs text-slate-600">{file.paper_format}</span>
            )}
            <span className="text-xs text-slate-700">
              {(file.file_size / 1024).toFixed(0)} KB
            </span>
          </div>
        </div>
      </div>

      {/* Preview */}
      {isImage && (
        <div className="mb-2 rounded overflow-hidden bg-slate-900">
          <img
            src={getFileUrl(file.job_id, file.id)}
            alt={file.original_name}
            className="max-h-48 w-auto mx-auto object-contain"
            loading="lazy"
          />
        </div>
      )}

      {/* Кнопки */}
      <div className="flex gap-2">
        <button
          onClick={onDownload}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs',
            'bg-slate-700 hover:bg-slate-600 text-slate-300',
            'transition-colors min-h-[36px]'
          )}
        >
          <Download size={12} />
          {t('job.download')}
        </button>
        {isPdf && (
          <a
            href={getFileUrl(file.job_id, file.id)}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs',
              'bg-slate-700 hover:bg-slate-600 text-slate-300',
              'transition-colors min-h-[36px]'
            )}
          >
            <ExternalLink size={12} />
            {t('job.open')}
          </a>
        )}
      </div>
    </div>
  )
}

function DrawerSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      {[1, 2, 3].map((s) => (
        <div key={s}>
          <div className="h-3 w-28 bg-slate-800 rounded mb-3" />
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-3 w-16 bg-slate-800 rounded" />
                <div className="h-3 w-24 bg-slate-800 rounded" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
