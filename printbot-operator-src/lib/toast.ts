// src/lib/toast.ts
// Мінімальна toast система через CustomEvent — без зовнішніх залежностей

export type ToastType = 'success' | 'error' | 'info'

export interface ToastPayload {
  id: string
  message: string
  type: ToastType
}

let counter = 0

export function showToast(message: string, type: ToastType = 'info') {
  const payload: ToastPayload = { id: String(++counter), message, type }
  window.dispatchEvent(new CustomEvent('printbot:toast', { detail: payload }))
}
