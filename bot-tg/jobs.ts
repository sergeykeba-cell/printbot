// src/api/jobs.ts
import { axiosClient } from './client'
import type { PrintJob, JobsPage, JobStatus, AuditPayload } from '@/types/printbot'

// ─── GET /jobs ────────────────────────────────────────────────────────────────
export async function getJobs(params: {
  status?: JobStatus
  limit?: number
  offset?: number
}): Promise<JobsPage> {
  const { data } = await axiosClient.get<any>('/jobs', { params })
  if (Array.isArray(data)) return { items: data, total: data.length }
  return data
}

// ─── GET /jobs/:id ────────────────────────────────────────────────────────────
export async function getJob(id: string): Promise<PrintJob> {
  const { data } = await axiosClient.get<PrintJob>(`/jobs/${id}`)
  return data
}

// ─── PATCH /jobs/:id ─────────────────────────────────────────────────────────
export async function patchJobStatus(id: string, status: JobStatus): Promise<PrintJob> {
  const { data } = await axiosClient.patch<PrintJob>(`/jobs/${id}`, { status })
  return data
}

// ─── DELETE /jobs/:id ────────────────────────────────────────────────────────
export async function deleteJob(id: string): Promise<void> {
  await axiosClient.delete(`/jobs/${id}`)
}

// ─── GET /jobs/:jobId/file/:fileId — URL для завантаження ────────────────────
export function getFileUrl(jobId: string, fileId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? ''
  const key = sessionStorage.getItem('api_key') ?? ''
  // Браузер завантажує файл напряму → ключ у query (тільки для download link)
  return `${base}/api/print/files/${fileId}/download?api_key=${encodeURIComponent(key)}`
}

// ─── GET /jobs/:jobId/file/:fileId/preview ────────────────────────────────────
export function getFilePreviewUrl(jobId: string, fileId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? ''
  const key = sessionStorage.getItem('api_key') ?? ''
  return `${base}/api/print/files/${fileId}/download?api_key=${encodeURIComponent(key)}`
}

// ─── POST /jobs/:id/audit ─────────────────────────────────────────────────────
export async function auditJobAction(id: string, payload: AuditPayload): Promise<void> {
  try {
    await axiosClient.post(`/jobs/${id}/audit`, payload)
  } catch {
    // Якщо ендпоінт ще не реалізований — тихо логуємо
    console.info('[audit]', id, payload)
  }
}

// ─── POST /jobs/reorder (Фаза 10) ────────────────────────────────────────────
export async function reorderJobs(orderedIds: string[]): Promise<void> {
  await axiosClient.post('/jobs/reorder', { ordered_ids: orderedIds })
}
