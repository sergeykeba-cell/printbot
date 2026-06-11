// src/api/client.ts
import axios, { AxiosError } from 'axios'

// Буде замінено на Bearer token у Фазі 13.
// Зараз: API ключ з sessionStorage → X-API-Key header.
export const axiosClient = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/print`,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Request interceptor: додаємо X-API-Key ──────────────────────────────────
axiosClient.interceptors.request.use((config) => {
  const key = sessionStorage.getItem('api_key')
  if (key) config.headers['X-API-Key'] = key
  return config
})

// ─── Response interceptor: 401/403 → logout ──────────────────────────────────
axiosClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      // Імпортуємо lazily щоб уникнути циклічних залежностей store → client → store
      import('@/stores/authStore').then(({ useAuthStore }) => {
        useAuthStore.getState().logout()
      })
    }
    return Promise.reject(error)
  }
)

// ─── Типізована помилка API ───────────────────────────────────────────────────
export interface ApiError {
  detail: string
  status: number
}

export function isApiError(err: unknown): err is AxiosError<ApiError> {
  return axios.isAxiosError(err)
}

export function getErrorMessage(err: unknown): string {
  if (isApiError(err)) {
    return err.response?.data?.detail ?? err.message
  }
  return 'Невідома помилка'
}
