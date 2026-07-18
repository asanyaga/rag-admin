import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ExternalLink } from 'lucide-react'
import type { ParseAgentRunStep } from '@/types/parseAgent'

interface StepDetailPanelProps {
  step: ParseAgentRunStep | null
}

export function StepDetailPanel({ step }: StepDetailPanelProps): JSX.Element {
  if (!step) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Select a step to inspect what it read and wrote.
      </p>
    )
  }

  const parseRunId = step.stateDelta['parse_run_id']

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">{step.node}</h3>
        <Badge variant="outline">{step.status}</Badge>
      </div>
      <Separator />
      <div>
        <p className="text-xs uppercase text-muted-foreground">input keys</p>
        <p className="font-mono text-sm">{step.inputKeys.join(', ') || '—'}</p>
      </div>
      <div>
        <p className="text-xs uppercase text-muted-foreground">output keys</p>
        <p className="font-mono text-sm">{step.outputKeys.join(', ') || '—'}</p>
      </div>
      <div>
        <p className="text-xs uppercase text-muted-foreground">state delta</p>
        <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">
          {JSON.stringify(step.stateDelta, null, 2)}
        </pre>
      </div>
      {step.durationMs !== null ? (
        <p className="text-xs text-muted-foreground">
          duration: {step.durationMs} ms
        </p>
      ) : null}
      {typeof parseRunId === 'string' ? (
        <Link
          to={`/parse-runs/${encodeURIComponent(parseRunId)}`}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          Open parsed document in results viewer
          <ExternalLink className="h-3 w-3" />
        </Link>
      ) : null}
    </div>
  )
}
