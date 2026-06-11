// src/pages/DashboardPage.tsx
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Printer, Volume2, VolumeX, Moon, Sun, LogOut, Keyboard } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import { useJobsQueue } from '@/hooks/useJobsQueue'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { OfflineBanner } from '@/components/OfflineBanner'
import { FiltersBar } from '@/components/FiltersBar'
import { JobsQueue } from '@/components/JobsQueue'
import { ShortcutOverlay } from '@/components/ShortcutOverlay'
import { cn } from '@/lib/cn'

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const logout = useAuthStore((s) => s.logout)
  const { audioEnabled, toggleAudio, theme, setTheme, setOnline, selectedJobId, setSelectedJobId } = useUiStore()

  const [showShortcuts, setShowShortcuts] = useState(false)

  // Дані черги потрібні для keyboard nav
  const { jobs } = useJobsQueue()

  useKeyboardShortcuts({
    jobs,
    onOpenShortcuts: () => setShowShortcuts(true),
    onOpenDrawer: () => {
      // Drawer відкривається автоматично коли selectedJobId != null —
      // тут просто переконуємось що він вже виставлений
      if (!selectedJobId && jobs.length > 0) {
        setSelectedJobId(jobs[0].id)
      }
    },
  })

  // Слухаємо online/offline
  useEffect(() => {
    const onOnline  = () => setOnline(true)
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [setOnline])

  // Застосовуємо dark/light клас при монтуванні
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'uk' ? 'ru' : 'uk')
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <OfflineBanner />

      {/* Header */}
      <header className="sticky top-0 z-30 bg-slate-900/80 backdrop-blur-sm border-b border-slate-800">
        <div className="max-w-screen-xl mx-auto px-4 h-14 flex items-center gap-3">
          <div className="flex items-center gap-2 mr-auto">
            <Printer size={20} className="text-sky-400" />
            <span className="font-semibold text-sm">PrintBot</span>
          </div>

          <nav className="flex items-center gap-1" aria-label="Панель керування">
            {/* Мова */}
            <button
              onClick={toggleLang}
              className={cn(
                'px-2 py-1.5 rounded-lg text-xs font-mono font-medium uppercase',
                'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
                'transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center'
              )}
              aria-label={t('nav.lang')}
            >
              {i18n.language === 'uk' ? 'UK' : 'RU'}
            </button>

            {/* Shortcuts hint */}
            <button
              onClick={() => setShowShortcuts(true)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-300
                         hover:bg-slate-800 transition-colors min-h-[36px] min-w-[36px]
                         flex items-center justify-center"
              aria-label={t('shortcuts.title')}
              title="? — клавіатурні скорочення"
            >
              <Keyboard size={15} />
            </button>

            {/* Звук */}
            <button
              onClick={toggleAudio}
              className={cn(
                'p-2 rounded-lg transition-colors min-h-[36px] min-w-[36px]',
                'flex items-center justify-center',
                audioEnabled
                  ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  : 'text-slate-600 hover:text-slate-500 hover:bg-slate-800'
              )}
              aria-label={audioEnabled ? t('nav.audio_on') : t('nav.audio_off')}
              title={audioEnabled ? t('nav.audio_on') : t('nav.audio_off')}
            >
              {audioEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>

            {/* Тема */}
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200
                         hover:bg-slate-800 transition-colors min-h-[36px] min-w-[36px]
                         flex items-center justify-center"
              aria-label={theme === 'dark' ? t('nav.theme_light') : t('nav.theme_dark')}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* Logout */}
            <button
              onClick={logout}
              className="p-2 rounded-lg text-slate-400 hover:text-red-400
                         hover:bg-slate-800 transition-colors min-h-[36px] min-w-[36px]
                         flex items-center justify-center"
              aria-label={t('nav.logout')}
              title={t('nav.logout')}
            >
              <LogOut size={16} />
            </button>
          </nav>
        </div>
      </header>

      {/* Filters */}
      <div className="sticky top-14 z-20 bg-slate-950/90 backdrop-blur-sm border-b border-slate-800/50">
        <div className="max-w-screen-xl mx-auto px-4">
          <FiltersBar />
        </div>
      </div>

      {/* Main */}
      <main className="flex-1 max-w-screen-xl mx-auto w-full px-4 py-4">
        <JobsQueue />
      </main>

      {/* Shortcut overlay */}
      {showShortcuts && (
        <ShortcutOverlay onClose={() => setShowShortcuts(false)} />
      )}
    </div>
  )
}
