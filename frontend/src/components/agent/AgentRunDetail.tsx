import { useState } from 'react'
import type { AgentRun, AgentDefinition, AgentTool, SubmitReviewRequest, ResumeAgentRunRequest } from '@/types/agent'
import { AgentFlowGraph } from '@/components/agent/AgentFlowGraph'
import { ReviewForm } from '@/components/agent/ReviewForm'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { Loader2, ChevronDown, ChevronRight } from 'lucide-react'

interface AgentRunDetailProps {
  run: AgentRun | null
  agentDefinition: AgentDefinition | null
  tools?: AgentTool[]
  isLoading: boolean
  isResuming: boolean
  error: string | null
  onResume: (data: ResumeAgentRunRequest) => Promise<void>
}

export function AgentRunDetail({
  run,
  agentDefinition,
  tools = [],
  isLoading,
  isResuming,
  error,
  onResume,
}: AgentRunDetailProps) {
  const [stateOpen, setStateOpen] = useState(false)

  if (isLoading || !run) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const graphNodes = agentDefinition
    ? agentDefinition.definition.nodes.map((n) => ({
        name: n.id,
        label: n.tool,
      }))
    : []

  const extractedData =
    (run.currentState?.extracted_data as Record<string, unknown>) ?? null
  const reviewedData =
    (run.currentState?.reviewed_data as Record<string, unknown>) ?? null
  const finalData = reviewedData ?? extractedData

  // Generic results: project current_state onto the output keys the definition's
  // tools declare (the three-way contract's `outputs`). Covers parse and any
  // future tool without extraction-specific special-casing.
  const outputData: Record<string, unknown> = {}
  if (run.currentState && agentDefinition) {
    const bySlug = new Map(tools.map((t) => [t.slug, t]))
    const outputKeys = new Set<string>()
    for (const node of agentDefinition.definition.nodes) {
      bySlug.get(node.tool)?.outputs.forEach((k) => outputKeys.add(k))
    }
    for (const key of outputKeys) {
      if (key in run.currentState) outputData[key] = run.currentState[key]
    }
  }
  const hasOutputData = Object.keys(outputData).length > 0

  const handleReview = async (request: SubmitReviewRequest) => {
    await onResume({ resumeValue: { action: request.action, data: request.data } })
  }

  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className="flex items-center gap-3">
        <Badge
          variant={
            run.status === 'failed'
              ? 'destructive'
              : run.status === 'completed'
                ? 'default'
                : 'secondary'
          }
        >
          {run.status.replace('_', ' ')}
        </Badge>
        <span className="text-xs text-muted-foreground">
          Started {new Date(run.createdAt).toLocaleString()}
        </span>
      </div>

      {/* Flow graph */}
      {graphNodes.length > 0 && (
        <AgentFlowGraph
          nodes={graphNodes}
          currentStep={run.currentNode}
          status={run.status}
          height={120}
        />
      )}

      {/* Status-driven content */}
      {(run.status === 'pending' || run.status === 'running') && (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {run.status === 'pending' ? 'Waiting to start...' : 'Running...'}
          {run.currentNode && (
            <span className="font-mono">({run.currentNode})</span>
          )}
        </div>
      )}

      {run.status === 'waiting_for_input' && extractedData && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Review Extracted Data</h3>
          <ReviewForm
            extractedData={extractedData}
            isSubmitting={isResuming}
            onSubmit={handleReview}
          />
        </div>
      )}

      {run.status === 'waiting_for_input' && !extractedData && (
        <Alert>
          <AlertDescription>
            Waiting for input at node <span className="font-mono">{run.currentNode}</span>.
            No extracted data available to review.
          </AlertDescription>
        </Alert>
      )}

      {run.status === 'completed' && (finalData || hasOutputData) && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Results</h3>
          <pre className="rounded-lg border bg-gray-50 p-4 text-xs overflow-auto max-h-96">
            {JSON.stringify(finalData ?? outputData, null, 2)}
          </pre>
        </div>
      )}

      {run.status === 'completed' && !finalData && !hasOutputData && (
        <Alert>
          <AlertDescription>Run completed with no output data.</AlertDescription>
        </Alert>
      )}

      {run.status === 'failed' && (
        <Alert variant="destructive">
          <AlertDescription>
            {run.statusMessage || 'Run failed with no error message.'}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Raw state inspector */}
      {run.currentState && (
        <Collapsible open={stateOpen} onOpenChange={setStateOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground">
              {stateOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              Raw State
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-2 rounded-lg border bg-gray-50 p-4 text-xs overflow-auto max-h-96">
              {JSON.stringify(run.currentState, null, 2)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
