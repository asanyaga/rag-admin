import { Badge } from '@/components/ui/badge'
import { ChevronRight } from 'lucide-react'
import type { ParseAgentRunStatus, ParseAgentRunStep } from '@/types/parseAgent'

interface GraphStripProps {
  graphNodes: string[]
  steps: ParseAgentRunStep[]
  runStatus: ParseAgentRunStatus
  selectedNode: string | null
  onSelectNode: (node: string) => void
}

type NodeState = 'done' | 'running' | 'pending'

export function nodeState(
  node: string,
  graphNodes: string[],
  steps: ParseAgentRunStep[],
  runStatus: ParseAgentRunStatus
): NodeState {
  if (steps.some((s) => s.node === node)) return 'done'
  const firstPending = graphNodes.find((n) => !steps.some((s) => s.node === n))
  if (runStatus === 'running' && firstPending === node) return 'running'
  return 'pending'
}

const stateClass: Record<NodeState, string> = {
  done: 'border-emerald-500 text-emerald-600',
  running: 'border-amber-500 text-amber-600 animate-pulse',
  pending: 'border-dashed text-muted-foreground',
}

export function GraphStrip({
  graphNodes,
  steps,
  runStatus,
  selectedNode,
  onSelectNode,
}: GraphStripProps): JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border p-4">
      <Badge variant="outline" className="border-dashed text-muted-foreground">
        start
      </Badge>
      {graphNodes.map((node) => (
        <div key={node} className="flex items-center gap-2">
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <button type="button" onClick={() => onSelectNode(node)}>
            <Badge
              variant="outline"
              className={`${stateClass[nodeState(node, graphNodes, steps, runStatus)]} ${
                selectedNode === node ? 'ring-2 ring-primary' : ''
              }`}
            >
              {node}
            </Badge>
          </button>
        </div>
      ))}
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
      <Badge variant="outline" className="border-dashed text-muted-foreground">
        end
      </Badge>
    </div>
  )
}
