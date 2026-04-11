import { useState } from 'react'
import type { AgentRun, AgentDefinition, ResumeAgentRunRequest } from '@/types/agent'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Loader2, ChevronDown, ChevronRight } from 'lucide-react'

interface AgentRunDetailProps {
  run: AgentRun | null
  agentDefinition: AgentDefinition | null
  isLoading: boolean
  isResuming: boolean
  error: string | null
  onResume: (data: ResumeAgentRunRequest) => Promise<void>
}

export function AgentRunDetail({
  run,
  isLoading,
  isResuming,
  error,
  onResume,
}: AgentRunDetailProps) {
  const [stateOpen, setStateOpen] = useState(false)
  const [resumeJson, setResumeJson] = useState('{}')
  const [resumeJsonError, setResumeJsonError] = useState<string | null>(null)

  if (isLoading || !run) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const handleResume = async () => {
    setResumeJsonError(null)
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(resumeJson)
    } catch {
      setResumeJsonError('Invalid JSON — please fix before resuming.')
      return
    }
    await onResume({ resumeValue: parsed })
  }

  const currentStateData =
    run.currentState && Object.keys(run.currentState).length > 0
      ? run.currentState
      : null

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

      {run.status === 'waiting_for_input' && (
        <div className="space-y-3 rounded-lg border p-4">
          <div>
            <h3 className="text-sm font-medium">Resume Run</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Waiting for input at node{' '}
              <span className="font-mono">{run.currentNode}</span>. Provide a
              JSON resume value below.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Resume Value (JSON)</Label>
            <Textarea
              className="font-mono text-xs"
              rows={6}
              value={resumeJson}
              onChange={(e) => setResumeJson(e.target.value)}
              placeholder="{}"
            />
            {resumeJsonError && (
              <p className="text-xs text-destructive">{resumeJsonError}</p>
            )}
          </div>
          <Button
            size="sm"
            onClick={handleResume}
            disabled={isResuming}
          >
            {isResuming ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Resuming...
              </>
            ) : (
              'Resume'
            )}
          </Button>
        </div>
      )}

      {run.status === 'completed' && currentStateData && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Results</h3>
          <pre className="rounded-lg border bg-gray-50 p-4 text-xs overflow-auto max-h-96">
            {JSON.stringify(currentStateData, null, 2)}
          </pre>
        </div>
      )}

      {run.status === 'completed' && !currentStateData && (
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
