import { useParams, useNavigate } from 'react-router-dom'
import { useAgentReceipt } from '@/hooks/useAgentReceipt'
import { ReceiptDetail } from '@/components/agent/ReceiptDetail'
import { Button } from '@/components/ui/button'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import type { SubmitReviewRequest } from '@/types/agent'

export default function AgentReceiptPage(): JSX.Element {
  const { receiptId } = useParams<{ receiptId: string }>()
  const navigate = useNavigate()
  const { receipt, isLoading, isSubmitting, error, submitReview } =
    useAgentReceipt(receiptId || null)

  const handleSubmitReview = async (request: SubmitReviewRequest) => {
    try {
      await submitReview(request)
      if (request.action === 'reject') {
        toast.info('Receipt rejected')
      } else {
        toast.success('Receipt approved and exported')
      }
    } catch (err) {
      toast.error('Review submission failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/agent')}
          className="mb-2"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Agent
        </Button>
        <h1 className="text-lg font-semibold">Receipt Detail</h1>
      </div>

      <ReceiptDetail
        receipt={receipt}
        isLoading={isLoading}
        isSubmitting={isSubmitting}
        error={error}
        onSubmitReview={handleSubmitReview}
      />
    </div>
  )
}
