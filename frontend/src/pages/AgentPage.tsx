import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useAgentReceipts } from '@/hooks/useAgentReceipts'
import { ReceiptProcessForm } from '@/components/agent/ReceiptProcessForm'
import { ReceiptList } from '@/components/agent/ReceiptList'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Bot } from 'lucide-react'
import { toast } from 'sonner'
import type { StartProcessingRequest } from '@/types/agent'

export default function AgentPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const { documents, isLoading: documentsLoading } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)
  const {
    receipts,
    isLoading: receiptsLoading,
    isProcessing,
    error,
    startProcessing,
  } = useAgentReceipts(projectId)

  const handleProcess = async (request: StartProcessingRequest) => {
    try {
      await startProcessing(request)
      toast.success('Processing started', {
        description: 'Extracting data from receipt...',
      })
    } catch (err) {
      toast.error('Processing failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <h1 className="text-lg font-semibold">Agent</h1>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Process receipts through the extract → review → export pipeline
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Process form */}
      <div className="rounded-lg border p-4">
        <h2 className="text-sm font-medium mb-3">Process New Receipt</h2>
        <ReceiptProcessForm
          documents={documents}
          schemas={schemas}
          isProcessing={isProcessing || documentsLoading}
          onProcess={handleProcess}
        />
      </div>

      <Separator />

      {/* Receipt list */}
      <div>
        <h2 className="text-sm font-medium mb-3">
          Processed Receipts
          {receipts.length > 0 && (
            <span className="text-muted-foreground font-normal ml-1.5">
              ({receipts.length})
            </span>
          )}
        </h2>
        <ReceiptList receipts={receipts} isLoading={receiptsLoading} />
      </div>
    </div>
  )
}
