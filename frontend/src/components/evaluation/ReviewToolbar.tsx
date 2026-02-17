import type { ReviewStatus, GoldenSetQuery } from '@/types/golden-set'

interface ReviewToolbarProps {
  queries: GoldenSetQuery[]
  activeFilter: ReviewStatus | 'all'
  onFilterChange: (filter: ReviewStatus | 'all') => void
}

const FILTERS: { key: ReviewStatus | 'all'; label: string; color: string }[] = [
  { key: 'all', label: 'Total', color: 'bg-muted text-foreground' },
  { key: 'accepted', label: 'Accepted', color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400' },
  { key: 'pending', label: 'Pending', color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' },
  { key: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' },
  { key: 'edited', label: 'Edited', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
]

export function ReviewToolbar({ queries, activeFilter, onFilterChange }: ReviewToolbarProps) {
  const counts: Record<string, number> = {
    all: queries.length,
    accepted: queries.filter((q) => q.reviewStatus === 'accepted').length,
    pending: queries.filter((q) => q.reviewStatus === 'pending').length,
    rejected: queries.filter((q) => q.reviewStatus === 'rejected').length,
    edited: queries.filter((q) => q.reviewStatus === 'edited').length,
  }

  return (
    <div className="flex gap-2 flex-wrap">
      {FILTERS.map(({ key, label, color }) => {
        const count = counts[key] ?? 0
        if (key !== 'all' && count === 0) return null
        const isActive = activeFilter === key
        return (
          <button
            key={key}
            onClick={() => onFilterChange(key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              isActive
                ? `${color} ring-2 ring-offset-1 ring-primary/30`
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            <span>{label}</span>
            <span className="font-mono text-xs">{count}</span>
          </button>
        )
      })}
    </div>
  )
}
