import { useNavigate } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from './StatusBadge'
import type { AgentReceiptListItem } from '@/types/agent'

interface ReceiptListProps {
  receipts: AgentReceiptListItem[]
  isLoading: boolean
}

function extractField(data: Record<string, unknown> | null, field: string): string {
  if (!data) return '—'
  const value = data[field]
  if (value === null || value === undefined) return '—'
  return String(value)
}

export function ReceiptList({ receipts, isLoading }: ReceiptListProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (receipts.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        No receipts processed yet. Use the form above to start processing.
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Vendor</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead>Date</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {receipts.map((receipt) => (
          <TableRow
            key={receipt.id}
            className="cursor-pointer hover:bg-muted/50"
            onClick={() => navigate(`/agent/receipts/${receipt.id}`)}
          >
            <TableCell>
              <StatusBadge status={receipt.status} />
            </TableCell>
            <TableCell>{extractField(receipt.extractedData, 'vendor')}</TableCell>
            <TableCell className="text-right">
              {extractField(receipt.extractedData, 'total')}
            </TableCell>
            <TableCell>{extractField(receipt.extractedData, 'date')}</TableCell>
            <TableCell className="text-muted-foreground text-sm">
              {new Date(receipt.createdAt).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
