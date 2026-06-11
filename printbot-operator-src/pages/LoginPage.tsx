// src/pages/LoginPage.tsx
import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Printer, Volume2, VolumeX, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import { axiosClient } from '@/api/client'
import { cn } from '@/lib/cn'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const setAudioInitialized = useAuthStore((s) => s.setAudioInitialized)
  const audioEnabled = useUiStore((s) => s.audioEnabled)
  const toggleAudio = useUiStore((s) => s.toggleAudio)

  const [key, setKey] = useState('')
  const [instanceUrl, setInstanceUrl] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('instance') || sessionStorage.getItem('instance_url') || ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async () => {
    const trimmed = key.trim()
    if (!trimmed) {
      setError(t('login.error_empty'))
      inputRef.current?.focus()
      return
    }

    const trimmedUrl = instanceUrl.trim().replace(/\/+$/, '')
    if (!trimmedUrl) {
      setError('Введіть URL інстансу')
      return
    }

    setLoading(true)
    setError('')

    try {
      // Перевіряємо ключ запитом до /jobs?limit=1
      const { default: axios } = await import('axios')
      await axios.get(`${trimmedUrl}/api/print/jobs`, {
        params: { limit: 1 },
        headers: { 'X-API-Key': trimmed },
      })

      // Ключ валідний — ініціалізуємо AudioContext у межах user gesture
      try {
        const ctx = new AudioContext()
        await ctx.resume()
        setAudioInitialized()
        // Ctx тримаємо в window щоб не GC-нувся
        ;(window as unknown as Record<string, unknown>).__audioCtx = ctx
      } catch {
        // Браузер заблокував — не критично
      }

      login(trimmed, trimmedUrl)
      navigate('/', { replace: true })
    } catch {
      setError(t('login.error_invalid'))
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit()
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
            <Printer className="text-sky-400" size={28} />
          </div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            {t('login.title')}
          </h1>
          <p className="text-slate-400 text-sm">{t('login.subtitle')}</p>
        </div>

        {/* Form */}
        <div className="flex flex-col gap-3">
          <input
            type="url"
            value={instanceUrl}
            onChange={(e) => { setInstanceUrl(e.target.value); setError('') }}
            placeholder="https://printbot-manager.duckdns.org/instance/test-shop"
            className="w-full rounded-xl px-4 py-3 bg-slate-800 border border-slate-700 hover:border-slate-600 text-white placeholder:text-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-colors"
          />
          <input
            ref={inputRef}
            type="password"
            value={key}
            onChange={(e) => { setKey(e.target.value); setError('') }}
            onKeyDown={handleKeyDown}
            placeholder={t('login.placeholder')}
            autoFocus
            className={cn(
              'w-full rounded-xl px-4 py-3 bg-slate-800 border text-white',
              'placeholder:text-slate-500 font-mono text-sm',
              'focus:outline-none focus:ring-2 focus:ring-sky-500',
              'transition-colors',
              error
                ? 'border-red-500 focus:ring-red-500'
                : 'border-slate-700 hover:border-slate-600'
            )}
          />

          {error && (
            <p className="text-red-400 text-sm px-1" role="alert">
              {error}
            </p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className={cn(
              'w-full rounded-xl py-3 font-medium text-sm transition-all',
              'bg-sky-500 hover:bg-sky-400 text-white',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950',
              'disabled:opacity-60 disabled:cursor-not-allowed',
              'flex items-center justify-center gap-2 min-h-[44px]'
            )}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              t('login.submit')
            )}
          </button>

          {/* Audio toggle */}
          <button
            onClick={toggleAudio}
            className={cn(
              'flex items-center gap-2 justify-center text-sm py-2 rounded-lg',
              'transition-colors min-h-[44px]',
              audioEnabled
                ? 'text-slate-400 hover:text-slate-300'
                : 'text-slate-600 hover:text-slate-500'
            )}
          >
            {audioEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
            {t('login.enable_audio')}
          </button>
        </div>
      </div>
    </div>
  )
}
