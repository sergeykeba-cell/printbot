// src/hooks/useJobsQueue.ts
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { getJobs } from '@/api/jobs'
import { useUiStore } from '@/stores/uiStore'
import { useDebounce } from './useDebounce'
import type { JobStatus, PrintJob } from '@/types/printbot'

const PAGE_SIZE = 50

export function useJobsQueue() {
  const { statusFilter, searchQuery } = useUiStore()
  const triggerNewJobAlert = useUiStore((s) => s.triggerNewJobAlert)
  const queryClient = useQueryClient()

  const debouncedSearch = useDebounce(searchQuery.trim(), 300)

  // Зберігаємо ID першої сторінки для детекції нових job
  const prevTopIdsRef = useRef<Set<string>>(new Set())

  const status: JobStatus | undefined =
    statusFilter === 'all' ? undefined : statusFilter

  const query = useInfiniteQuery({
    queryKey: ['jobs', status, debouncedSearch],
    queryFn: async ({ pageParam = 0 }) => {
      const data = await getJobs({
        status,
        limit: PAGE_SIZE,
        offset: pageParam as number,
      })
      return data
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const fetched = allPages.reduce((s, p) => s + p.items.length, 0)
      return fetched < lastPage.total ? fetched : undefined
    },
    refetchInterval: () => {
      // polling тільки якщо WS недоступний — буде визначено в Фазі 8
      const wsConnected = (window as unknown as Record<string, boolean>).__wsConnected ?? false
      return wsConnected
        ? false
        : Number(import.meta.env.VITE_POLL_INTERVAL ?? 5000)
    },
    refetchOnWindowFocus: true,
    staleTime: 2_000,
  })

  // Детекція нових замовлень (перша сторінка)
  useEffect(() => {
    const firstPage = query.data?.pages[0]
    if (!firstPage) return

    const currentIds = new Set(firstPage.items.map((j) => j.id))

    if (prevTopIdsRef.current.size > 0) {
      const hasNew = [...currentIds].some((id) => !prevTopIdsRef.current.has(id))
      if (hasNew) triggerNewJobAlert()
    }

    prevTopIdsRef.current = currentIds
  }, [query.data?.pages, triggerNewJobAlert])

  // Зручний плаский список
  const jobs: PrintJob[] = query.data?.pages.flatMap((p) => p.items) ?? []

  // Фільтрація по debouncedSearch на клієнті (ID contains)
  const filteredJobs = debouncedSearch
    ? jobs.filter((j) =>
        j.id.toLowerCase().includes(debouncedSearch.toLowerCase())
      )
    : jobs

  return {
    jobs: filteredJobs,
    total: query.data?.pages[0]?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    refetch: query.refetch,
    queryClient,
  }
}
