import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useAgentReceipts } from '@/hooks/useAgentReceipts'
import { useAgentConfigs } from '@/hooks/useAgentConfigs'
import { ReceiptProcessForm } from '@/components/agent/ReceiptProcessForm'
import { ReceiptList } from '@/components/agent/ReceiptList'
import { AgentSetup } from '@/components/agent/AgentSetup'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Bot } from 'lucide-react'
import { toast } from 'sonner'
import type { StartProcessingRequest } from '@/types/agent'

export default function AgentPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const {
    agentTypes,
    configs,
    isLoading: configsLoading,
    error: configsError,
    enableAgentType,
    removeConfig,
  } = useAgentConfigs(projectId)

  const hasReceiptProcessing = configs.some(
    (c) => c.agentType === 'receipt-processing' && c.enabled
  )

  const { documents, isLoading: documentsLoading } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)
  const {
    receipts,
    isLoading: receiptsLoading,
    isProcessing,
    error: receiptsError,
    startProcessing,
  } = useAgentReceipts(hasReceiptProcessing ? projectId : null)

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

  const handleEnableAgent = async (agentType: string) => {
    try {
      await enableAgentType({ agentType })
      toast.success('Agent enabled')
    } catch (err) {
      toast.error('Failed to enable agent', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleRemoveAgent = async (configId: string) => {
    try {
      await removeConfig(configId)
      toast.success('Agent removed')
    } catch (err) {
      toast.error('Failed to remove agent', {
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

  const error = configsError || receiptsError

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <h1 className="text-lg font-semibold">Agent</h1>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Configure and run agent workflows for {currentProject.name}
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {configsLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : configs.length === 0 ? (
        /* No agents configured — show setup */
        <AgentSetup
          agentTypes={agentTypes}
          onEnable={handleEnableAgent}
        />
      ) : (
        /* Show configured agents */
        <div className="space-y-6">
          {/* Agent config management */}
          <AgentSetup
            agentTypes={agentTypes}
            configs={configs}
            onEnable={handleEnableAgent}
            onRemove={handleRemoveAgent}
          />

          {/* Receipt processing flow */}
          {hasReceiptProcessing && (
            <>
              <Separator />

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
            </>
          )}
        </div>
      )}
    </div>
  )
}
