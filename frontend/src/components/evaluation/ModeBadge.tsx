import { Badge } from '@/components/ui/badge'
import type { EvalMode } from '@/types/eval-run'

interface ModeBadgeProps {
  mode: EvalMode
  className?: string
}

export function ModeBadge({ mode, className }: ModeBadgeProps) {
  if (mode === 'retrieval_and_answer') {
    return (
      <Badge variant="default" className={`bg-purple-100 text-purple-800 hover:bg-purple-100 dark:bg-purple-900/30 dark:text-purple-400 ${className ?? ''}`}>
        Ret + Answer
      </Badge>
    )
  }

  return (
    <Badge variant="default" className={`bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400 ${className ?? ''}`}>
      Retrieval
    </Badge>
  )
}
