/**
 * Status badge for indexes
 */
import { IndexStatus } from '@/types/index'
import { Badge } from '@/components/ui/badge'
import { Loader2, CheckCircle, XCircle, Clock } from 'lucide-react'

interface IndexStatusBadgeProps {
  status: IndexStatus
  className?: string
}

const statusConfig: Record<
  IndexStatus,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning' | 'blue'; icon: React.ReactNode }
> = {
  created: {
    label: 'Draft',
    variant: 'outline',
    icon: <Clock className="h-3 w-3" />,
  },
  processing: {
    label: 'Processing',
    variant: 'blue',
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  ready: {
    label: 'Ready',
    variant: 'success',
    icon: <CheckCircle className="h-3 w-3" />,
  },
  failed: {
    label: 'Failed',
    variant: 'destructive',
    icon: <XCircle className="h-3 w-3" />,
  },
}

export function IndexStatusBadge({ status, className }: IndexStatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <Badge variant={config.variant} className={className}>
      <span className="flex items-center gap-1">
        {config.icon}
        {config.label}
      </span>
    </Badge>
  )
}
