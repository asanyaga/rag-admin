import { cn } from '@/lib/utils'

interface ScorePillProps {
  score: number | null
  className?: string
}

function scoreColor(val: number): string {
  if (val >= 0.8) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
  if (val >= 0.5) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
  return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
}

export function ScorePill({ score, className }: ScorePillProps) {
  if (score === null || score === undefined) {
    return <span className={cn('text-xs text-muted-foreground', className)}>—</span>
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-medium',
        scoreColor(score),
        className
      )}
    >
      {(score * 100).toFixed(0)}%
    </span>
  )
}
