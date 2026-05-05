// frontend/src/components/classification/ClassificationRunStatusBadge.tsx
import { Badge } from '@/components/ui/badge'
import type { ClassificationRunStatus } from '@/types/classification'

const STATUS_STYLES: Record<ClassificationRunStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

interface Props {
  status: ClassificationRunStatus
}

export function ClassificationRunStatusBadge({ status }: Props) {
  return (
    <Badge className={STATUS_STYLES[status]}>
      {status}
    </Badge>
  )
}
