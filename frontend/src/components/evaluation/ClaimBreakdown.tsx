import { cn } from '@/lib/utils'
import type { ClaimItem } from '@/types/eval-run'

interface ClaimBreakdownProps {
  claims: ClaimItem[]
}

const LABEL_STYLES: Record<string, { dot: string; text: string }> = {
  supported: {
    dot: 'bg-green-500',
    text: 'text-green-700 dark:text-green-400',
  },
  unsupported: {
    dot: 'bg-red-500',
    text: 'text-red-700 dark:text-red-400',
  },
  unclear: {
    dot: 'bg-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
  },
}

export function ClaimBreakdown({ claims }: ClaimBreakdownProps) {
  if (!claims || claims.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No claims extracted.</p>
    )
  }

  const supportedCount = claims.filter((c) => c.label === 'supported').length
  const unsupportedCount = claims.filter((c) => c.label === 'unsupported').length
  const unclearCount = claims.filter((c) => c.label === 'unclear').length

  return (
    <div className="space-y-3">
      {/* Count badges */}
      <div className="flex items-center gap-3 text-xs">
        {supportedCount > 0 && (
          <span className="text-green-700 dark:text-green-400">
            {supportedCount} supported
          </span>
        )}
        {unsupportedCount > 0 && (
          <span className="text-red-700 dark:text-red-400">
            {unsupportedCount} unsupported
          </span>
        )}
        {unclearCount > 0 && (
          <span className="text-amber-700 dark:text-amber-400">
            {unclearCount} unclear
          </span>
        )}
      </div>

      {/* Claim cards */}
      <div className="space-y-2">
        {claims.map((claim, i) => {
          const style = LABEL_STYLES[claim.label] ?? LABEL_STYLES.unclear
          return (
            <div
              key={i}
              className="flex items-start gap-3 p-3 rounded-lg border bg-card"
            >
              <div
                className={cn('mt-1.5 h-2 w-2 rounded-full shrink-0', style.dot)}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm">{claim.text}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={cn('text-xs font-medium capitalize', style.text)}
                  >
                    {claim.label}
                  </span>
                  {claim.source && (
                    <span className="text-xs text-muted-foreground">
                      Source: [{claim.source}]
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
