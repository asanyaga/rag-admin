import { Badge } from '@/components/ui/badge'

type StatusVariant = 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning' | 'blue'

const STATUS_MAP: Record<string, StatusVariant> = {
  draft: 'secondary',
  completed: 'success',
  pending: 'warning',
  running: 'blue',
  generating: 'blue',
  failed: 'destructive',
  ready: 'success',
}

interface EvalStatusBadgeProps {
  status: string
  className?: string
}

export function EvalStatusBadge({ status, className }: EvalStatusBadgeProps) {
  const variant = STATUS_MAP[status] ?? 'outline'
  return (
    <Badge variant={variant} className={className}>
      {status}
    </Badge>
  )
}
