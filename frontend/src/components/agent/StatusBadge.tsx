import { Badge } from '@/components/ui/badge'
import type { AgentReceiptStatus } from '@/types/agent'

const statusConfig: Record<
  AgentReceiptStatus,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; className: string }
> = {
  pending: { label: 'Pending', variant: 'secondary', className: 'bg-gray-100 text-gray-700' },
  extracting: { label: 'Extracting', variant: 'secondary', className: 'bg-blue-100 text-blue-700' },
  reviewing: { label: 'Needs Review', variant: 'default', className: 'bg-amber-100 text-amber-700' },
  approved: { label: 'Approved', variant: 'default', className: 'bg-green-100 text-green-700' },
  exported: { label: 'Exported', variant: 'default', className: 'bg-emerald-100 text-emerald-700' },
  failed: { label: 'Failed', variant: 'destructive', className: '' },
}

interface StatusBadgeProps {
  status: AgentReceiptStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status]
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.label}
    </Badge>
  )
}
