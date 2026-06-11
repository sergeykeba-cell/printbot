// src/components/JobCard.tsx
import { useTranslation } from 'react-i18next'
import { FileText, Image, File, Printer, Copy } from 'lucide-react'
import { StatusBadge } from './StatusBadge'
import { useUiStore } from '@/stores/uiStore'
import { cn } from '@/lib/cn'
import { format } from '@/lib/dateFormat'
import type { PrintJob, PrintedFile } from '@/types/printbot'

interface Props {
  job: PrintJob
  isSelected?: boolean
  onClick?: () => void
}

function FileIcon({ mime }: { mime: string }) {
  if (mime.startsWith('image/'))         return <Image    size={12} className="text-sky-400" />
  if (mime === 'application/pdf')        return <FileText size={12} className="text-red-400" />
  return                                        <File     size={12} className="text-slate-400" />
}

export function JobCard({ job, isSelected, onClick }: Props) {
  const { t } = useTranslation()
  const setSelectedJobId = useUiStore((s) => s.setSelectedJobId)

  const handleClick = () => {
    setSelectedJobId(job.id)
    onClick?.()
  }

  const shortId    = job.id.slice(0, 8).toUpperCase()
  const totalPages = job.files.reduce((s, f) => s + (f.page_count ?? 0), 0)

  const colorLabel = job.color_mode === 'color'
    ? t('job.color_label')
    : t('job.bw_label')

  const duplexLabel =
    job.duplex === 'one_sided'       ? t('job.duplex_one') :
    job.duplex === 'two_sided_long'  ? t('job.duplex_long') :
                                              t('job.duplex_short')

  return (
    <article
      role="button"
      tabIndex={0}
      aria-selected={isSelected}
      aria-label={`${t('job.id')} ${shortId}, ${t('job.status')}: ${t(`status.${job.status}`)}`}
      onClick={handleClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick() }}
      className={cn(
        'rounded-xl border p-3.5 cursor-pointer select-none',
        'transition-all duration-150 outline-none',
        'focus-visible:ring-2 focus-visible:ring-sky-500',
        isSelected
          ? 'bg-slate-800 border-sky-500/50 shadow-lg shadow-sky-500/5'
          : 'bg-slate-900 border-slate-800 hover:bg-slate-800/70 hover:border-slate-700'
      )}
    >
      {/* Row 1: ID + статус + час */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <span className="font-mono text-xs text-slate-400 tracking-wider">
          #{shortId}
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-slate-600">{format(job.created_at)}</span>
          <StatusBadge status={job.status} />
        </div>
      </div>

      {/* Row 2: Telegram user */}
      <div className="flex items-center gap-1.5 mb-3">
        <span className="text-xs text-slate-500">tg:</span>
        <span className="text-xs text-slate-300 font-mono">{job.user_id}</span>
      </div>

      {/* Files */}
      {job.files.length > 0 ? (
        <div className="flex flex-col gap-1 mb-3">
          {job.files.map((f: PrintedFile) => (
            <div key={f.id} className="flex items-center gap-1.5">
              <FileIcon mime={f.mime_type} />
              <span className="text-xs text-slate-400 truncate flex-1 min-w-0">
                {f.original_name}
              </span>
              {f.page_count != null && (
                <span className="text-xs text-slate-600 flex-shrink-0">
                  {f.page_count} {t('job.pages')}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-600 mb-3">{t('job.no_files')}</p>
      )}

      {/* Row 3: параметри друку */}
      <div className="flex items-center gap-2 flex-wrap">
        <Chip>{colorLabel}</Chip>
        <Chip>{duplexLabel}</Chip>

        {job.copies > 1 && (
          <Chip>
            <Copy size={10} className="mr-0.5" />
            {t('job.copies', { count: job.copies })}
          </Chip>
        )}

        {job.files[0]?.paper_format && (
          <Chip>{job.files[0]?.paper_format}</Chip>
        )}

        {totalPages > 0 && (
          <Chip>
            <Printer size={10} className="mr-0.5" />
            {totalPages} {t('job.pages')}
          </Chip>
        )}
      </div>
    </article>
  )
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs
                     bg-slate-800 text-slate-400 border border-slate-700/50">
      {children}
    </span>
  )
}
