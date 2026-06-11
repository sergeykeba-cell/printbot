// src/lib/dateFormat.ts
import i18n from '@/lib/i18n'

/** HH:MM для сьогодні, "вчора HH:MM", або "DD.MM HH:MM" */
export function format(iso: string): string {
  const d = new Date(iso)
  const now = new Date()

  const hhmm = d.toLocaleTimeString(i18n.language === 'ru' ? 'ru-RU' : 'uk-UA', {
    hour: '2-digit',
    minute: '2-digit',
  })

  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear()

  if (sameDay) return hhmm

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const isYesterday =
    d.getDate() === yesterday.getDate() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getFullYear() === yesterday.getFullYear()

  if (isYesterday) return `${i18n.t('date.yesterday')} ${hhmm}`

  return (
    d.toLocaleDateString(i18n.language === 'ru' ? 'ru-RU' : 'uk-UA', {
      day: '2-digit',
      month: '2-digit',
    }) +
    ' ' +
    hhmm
  )
}

/** Повна дата + час для drawer */
export function formatFull(iso: string): string {
  return new Date(iso).toLocaleString(i18n.language === 'ru' ? 'ru-RU' : 'uk-UA', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
