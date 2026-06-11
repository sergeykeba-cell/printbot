// src/hooks/useNewJobSound.ts
import { useEffect, useRef } from 'react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'

// Генеруємо короткий beep через Web Audio API
// — не потребує зовнішнього MP3 файлу
function playBeep(ctx: AudioContext) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()

  osc.connect(gain)
  gain.connect(ctx.destination)

  osc.type = 'sine'
  osc.frequency.setValueAtTime(880, ctx.currentTime)
  osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15)

  gain.gain.setValueAtTime(0.3, ctx.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25)

  osc.start(ctx.currentTime)
  osc.stop(ctx.currentTime + 0.25)
}

export function useNewJobSound() {
  const newJobAlert = useUiStore((s) => s.newJobAlert)
  const audioEnabled = useUiStore((s) => s.audioEnabled)
  const audioInitialized = useAuthStore((s) => s.audioInitialized)
  const mountedRef = useRef(false)

  useEffect(() => {
    // Пропускаємо перший рендер (початковий стан = 0)
    if (!mountedRef.current) {
      mountedRef.current = true
      return
    }
    if (!audioEnabled || !audioInitialized) return

    const ctx = (window as unknown as Record<string, AudioContext>).__audioCtx
    if (!ctx) return

    try {
      playBeep(ctx)
    } catch {
      // AudioContext може бути suspended після довгої неактивності
      ctx.resume().then(() => playBeep(ctx)).catch(() => {})
    }
  }, [newJobAlert, audioEnabled, audioInitialized])
}
