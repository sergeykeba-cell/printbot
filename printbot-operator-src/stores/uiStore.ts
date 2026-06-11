// src/stores/uiStore.ts
import { create } from 'zustand'
import type { JobStatus } from '@/types/printbot'

interface UiState {
  // Фільтри черги
  statusFilter: JobStatus | 'all'
  searchQuery: string

  // Вибраний job (drawer + keyboard nav)
  selectedJobId: string | null

  // Звук
  audioEnabled: boolean

  // Мережа
  isOnline: boolean

  // Нове замовлення — тригер для toast + звуку
  newJobAlert: number   // інкрементується при кожному новому job

  // Тема
  theme: 'dark' | 'light'

  // Actions
  setStatusFilter: (f: JobStatus | 'all') => void
  setSearchQuery: (q: string) => void
  setSelectedJobId: (id: string | null) => void
  toggleAudio: () => void
  setOnline: (v: boolean) => void
  triggerNewJobAlert: () => void
  setTheme: (t: 'dark' | 'light') => void
}

// Ініціалізація теми з localStorage / prefers-color-scheme
function getInitialTheme(): 'dark' | 'light' {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useUiStore = create<UiState>((set) => ({
  statusFilter: 'all',
  searchQuery: '',
  selectedJobId: null,
  audioEnabled: true,
  isOnline: navigator.onLine,
  newJobAlert: 0,
  theme: getInitialTheme(),

  setStatusFilter: (f) => set({ statusFilter: f, selectedJobId: null }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setSelectedJobId: (id) => set({ selectedJobId: id }),
  toggleAudio: () => set((s) => ({ audioEnabled: !s.audioEnabled })),
  setOnline: (v) => set({ isOnline: v }),
  triggerNewJobAlert: () => set((s) => ({ newJobAlert: s.newJobAlert + 1 })),
  setTheme: (t) => {
    localStorage.setItem('theme', t)
    document.documentElement.classList.toggle('dark', t === 'dark')
    set({ theme: t })
  },
}))
