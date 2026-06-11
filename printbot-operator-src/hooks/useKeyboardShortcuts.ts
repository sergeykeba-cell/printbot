// src/hooks/useKeyboardShortcuts.ts
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMutation } from '@tanstack/react-query'
import { useUiStore } from '@/stores/uiStore'
import { patchJobStatus } from '@/api/jobs'

interface Options {
  jobs: { id: string }[]
  onOpenShortcuts: () => void
  onOpenDrawer: () => void
}

export function useKeyboardShortcuts({ jobs, onOpenShortcuts, onOpenDrawer }: Options) {
  const { selectedJobId, setSelectedJobId } = useUiStore()
  const queryClient = useQueryClient()

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'printed' | 'failed' }) =>
      patchJobStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.ctrlKey || e.metaKey || e.altKey) return

      switch (e.key) {
        case 'ArrowDown': {
          e.preventDefault()
          if (jobs.length === 0) return
          if (!selectedJobId) {
            setSelectedJobId(jobs[0].id)
          } else {
            const idx = jobs.findIndex((j) => j.id === selectedJobId)
            if (idx < jobs.length - 1) setSelectedJobId(jobs[idx + 1].id)
          }
          break
        }
        case 'ArrowUp': {
          e.preventDefault()
          if (!selectedJobId) return
          const idx = jobs.findIndex((j) => j.id === selectedJobId)
          if (idx > 0) setSelectedJobId(jobs[idx - 1].id)
          break
        }
        case 'Enter': {
          e.preventDefault()
          if (selectedJobId) onOpenDrawer()
          break
        }
        case 'p':
        case 'P': {
          e.preventDefault()
          if (!selectedJobId || statusMutation.isPending) return
          statusMutation.mutate({ id: selectedJobId, status: 'printed' })
          break
        }
        case 'f':
        case 'F': {
          e.preventDefault()
          if (!selectedJobId || statusMutation.isPending) return
          statusMutation.mutate({ id: selectedJobId, status: 'failed' })
          break
        }
        case 'Escape': {
          setSelectedJobId(null)
          break
        }
        case 'r':
        case 'R': {
          e.preventDefault()
          queryClient.invalidateQueries({ queryKey: ['jobs'] })
          break
        }
        case '?': {
          e.preventDefault()
          onOpenShortcuts()
          break
        }
        default:
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [
    jobs, selectedJobId, setSelectedJobId,
    queryClient, onOpenShortcuts, onOpenDrawer,
    statusMutation,
  ])
}
