import { DocumentStatus } from '@/types/document'
import { Badge } from '@/components/ui/badge'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'

interface DocumentStatusBadgeProps {
  status: DocumentStatus
  className?: string
}

const statusConfig: Record<
  DocumentStatus,
  { label: string; variant: 'destructive' | 'outline' | 'success' | 'blue'; icon: React.ReactNode }
> = {
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

export function DocumentStatusBadge({
  status,
  className,
}: DocumentStatusBadgeProps) {
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
