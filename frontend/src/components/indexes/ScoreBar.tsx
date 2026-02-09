/**
 * Visual score indicator bar with color-coded thresholds
 */
import { cn } from '@/lib/utils'

interface ScoreBarProps {
  score: number
}

export function getScoreColor(score: number) {
  if (score >= 0.85) return { bar: 'bg-emerald-500', text: 'text-emerald-600' }
  if (score >= 0.7) return { bar: 'bg-yellow-500', text: 'text-yellow-600' }
  if (score >= 0.5) return { bar: 'bg-orange-500', text: 'text-orange-600' }
  return { bar: 'bg-red-500', text: 'text-red-600' }
}

export function ScoreBar({ score }: ScoreBarProps) {
  const pct = score * 100
  const colors = getScoreColor(score)

  return (
    <div className="flex items-center gap-2">
      <div
        className="w-16 h-1.5 bg-zinc-100 rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-label={`Similarity score: ${score.toFixed(2)}`}
      >
        <div
          className={cn('h-full rounded-full transition-all duration-500', colors.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn('text-xs font-mono font-semibold', colors.text)}>
        {score.toFixed(2)}
      </span>
    </div>
  )
}
