// src/stores/authStore.ts
import { create } from 'zustand'

interface AuthState {
  apiKey: string | null
  instanceUrl: string | null
  isAuthenticated: boolean
  audioInitialized: boolean
  login: (key: string, instanceUrl: string) => void
  logout: () => void
  setAudioInitialized: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  // Відновлюємо сесію при перезавантаженні сторінки
  apiKey: sessionStorage.getItem('api_key'),
  instanceUrl: sessionStorage.getItem('instance_url'),
  isAuthenticated: Boolean(sessionStorage.getItem('api_key')),
  audioInitialized: false,

  login: (key) => {
    sessionStorage.setItem('api_key', key)
    set({ apiKey: key, isAuthenticated: true })
  },

  logout: () => {
    sessionStorage.removeItem('api_key')
    set({ apiKey: null, isAuthenticated: false, audioInitialized: false })
    // Редирект через window щоб не залежати від react-router тут
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  },

  setAudioInitialized: () => set({ audioInitialized: true }),
}))
