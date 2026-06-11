// src/types/printbot.ts
// Відповідає моделям SQLAlchemy з models.py

export type JobStatus =
  | 'draft'
  | 'processing'
  | 'ready_to_print'
  | 'printed'
  | 'failed'

export type FileStatus =
  | 'uploaded'
  | 'processing'
  | 'ready_to_print'
  | 'failed'

export type ColorMode = 'color' | 'bw'
export type DuplexMode = 'one_sided' | 'two_sided_long' | 'two_sided_short'
export type PhotoSize = '10x15' | '13x18' | '15x21' | 'a4'
export type PaperFormat = 'A4' | 'A3' | 'Letter'

export interface PrintConfig {
  color_mode: ColorMode
  duplex: DuplexMode
  copies: number
  photo_size?: PhotoSize
  paper_format?: PaperFormat
}

export interface PrintedFile {
  id: string
  job_id: string
  original_name: string
  file_path: string
  mime_type: string
  file_size: number          // bytes
  status: FileStatus
  page_count?: number
  paper_format?: PaperFormat
  is_color?: boolean
  preview_url?: string       // після DOCX→PDF конвертації (Фаза 12)
  created_at: string         // ISO 8601
  updated_at: string
}

export interface PrintJob {
  id: string
  user_id: number            // Telegram user_id
  shop_id: string            // multitenant
  status: JobStatus
  config: PrintConfig
  files: PrintedFile[]
  priority: number           // для DnD (Фаза 10)
  created_at: string
  updated_at: string
}

// Відповідь від GET /jobs (пагінована)
export interface JobsPage {
  items: PrintJob[]
  total: number
  limit: number
  offset: number
}

// WS event (Фаза 8)
export type WsEventType = 'job_created' | 'job_updated' | 'job_deleted' | 'auth_ok' | 'auth_error'

export interface WsEvent {
  event: WsEventType
  job_id?: string
  status?: JobStatus
  updated_at?: string
}

// Audit (Фаза 3)
export type AuditAction = 'file_download' | 'status_changed' | 'job_deleted'

export interface AuditPayload {
  action: AuditAction
  new_status?: JobStatus
}
