import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useAgentReceipts } from '@/hooks/useAgentReceipts'
import { useAgentConfigs } from '@/hooks/useAgentConfigs'
import { useFlowDefinitions } from '@/hooks/useFlowDefinitions'
import { ReceiptProcessForm } from '@/components/agent/ReceiptProcessForm'
import { ReceiptList } from '@/components/agent/ReceiptList'
import { FlowList } from '@/components/agent/FlowList'
import { AgentSetup } from '@/components/agent/AgentSetup'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Bot, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import type { StartProcessingRequest } from '@/types/agent'

export default function AgentPage(): JSX.Element {
  const navigate = useNavigate()
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

  const {
    flows,
    isLoading: flowsLoading,
    deleteFlow,
  } = useFlowDefinitions(projectId)

  const handleDeleteFlow = async (flowId: string) => {
    try {
      await deleteFlow(flowId)
      toast.success('Flow deleted')
    } catch (err) {
      toast.error('Failed to delete flow', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

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
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            <h1 className="text-lg font-semibold">Agent</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Configure and run agent workflows for {currentProject.name}
          </p>
        </div>
        <Button size="sm" onClick={() => navigate('/agent/flows/new')}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Flow
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Flows */}
      <div>
        <h2 className="text-sm font-medium mb-3">
          Flows
          {flows.length > 0 && (
            <span className="text-muted-foreground font-normal ml-1.5">
              ({flows.length})
            </span>
          )}
        </h2>
        <FlowList
          flows={flows}
          isLoading={flowsLoading}
          onDelete={handleDeleteFlow}
        />
      </div>

      <Separator />

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
