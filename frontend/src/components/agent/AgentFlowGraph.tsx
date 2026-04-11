import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { AgentReceiptStatus, FlowRunStatus } from '@/types/agent'

interface AgentFlowGraphProps {
  nodes: { name: string; label: string }[]
  currentStep?: string | null
  status?: AgentReceiptStatus | null
  flowRunStatus?: FlowRunStatus | null
  height?: number
}

type NodeStatus = 'completed' | 'active' | 'pending' | 'failed'

function getNodeStatus(
  _nodeName: string,
  nodeIndex: number,
  nodes: { name: string }[],
  currentStep: string | null,
  status: AgentReceiptStatus | null,
  flowRunStatus: FlowRunStatus | null = null
): NodeStatus {
  // Generic flow run status handling
  if (flowRunStatus) {
    if (flowRunStatus === 'completed') return 'completed'
    if (flowRunStatus === 'failed') {
      const currentIndex = nodes.findIndex((n) => n.name === currentStep)
      if (nodeIndex < currentIndex) return 'completed'
      if (nodeIndex === currentIndex) return 'failed'
      return 'pending'
    }
    if (flowRunStatus === 'pending') return 'pending'
    // running or waiting_for_input
    const currentIndex = nodes.findIndex((n) => n.name === currentStep)
    if (currentIndex < 0) return nodeIndex === 0 ? 'active' : 'pending'
    if (nodeIndex < currentIndex) return 'completed'
    if (nodeIndex === currentIndex) return 'active'
    return 'pending'
  }

  // Receipt-specific status handling
  if (!status || !currentStep) return 'pending'
  if (status === 'failed') {
    const currentIndex = nodes.findIndex((n) => n.name === currentStep)
    if (nodeIndex < currentIndex) return 'completed'
    if (nodeIndex === currentIndex) return 'failed'
    return 'pending'
  }

  // Map receipt status to which step is "current"
  const statusToStep: Record<string, string> = {
    pending: '',
    extracting: 'extract',
    reviewing: 'review',
    approved: 'export',
    exported: 'export',
  }
  const activeStep = statusToStep[status] || currentStep
  const activeIndex = nodes.findIndex((n) => n.name === activeStep)

  if (status === 'exported' || status === 'approved') return 'completed'
  if (nodeIndex < activeIndex) return 'completed'
  if (nodeIndex === activeIndex) return 'active'
  return 'pending'
}

const statusColors: Record<NodeStatus, { bg: string; border: string; text: string }> = {
  completed: { bg: 'bg-emerald-50', border: 'border-emerald-400', text: 'text-emerald-700' },
  active: { bg: 'bg-blue-50', border: 'border-blue-400', text: 'text-blue-700' },
  pending: { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-400' },
  failed: { bg: 'bg-red-50', border: 'border-red-400', text: 'text-red-700' },
}

const statusIcons: Record<NodeStatus, string> = {
  completed: '✓',
  active: '●',
  pending: '○',
  failed: '✕',
}

function FlowNode({ data }: { data: { label: string; nodeStatus: NodeStatus } }) {
  const colors = statusColors[data.nodeStatus]
  const icon = statusIcons[data.nodeStatus]
  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 ${colors.bg} ${colors.border} min-w-[140px] text-center shadow-sm`}
    >
      <div className={`text-xs font-mono mb-1 ${colors.text}`}>{icon}</div>
      <div className={`text-sm font-medium ${colors.text}`}>{data.label}</div>
    </div>
  )
}

const nodeTypes = { flowNode: FlowNode }

export function AgentFlowGraph({
  nodes: graphNodes,
  currentStep = null,
  status = null,
  flowRunStatus = null,
  height = 120,
}: AgentFlowGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const NODE_WIDTH = 160
    const NODE_SPACING = 80
    const totalWidth = graphNodes.length * NODE_WIDTH + (graphNodes.length - 1) * NODE_SPACING
    const startX = -totalWidth / 2 + NODE_WIDTH / 2

    const rfNodes: Node[] = graphNodes.map((node, i) => ({
      id: node.name,
      type: 'flowNode',
      position: { x: startX + i * (NODE_WIDTH + NODE_SPACING), y: 0 },
      data: {
        label: node.label,
        nodeStatus: getNodeStatus(node.name, i, graphNodes, currentStep, status, flowRunStatus),
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }))

    const rfEdges: Edge[] = graphNodes.slice(0, -1).map((node, i) => {
      const sourceStatus = getNodeStatus(node.name, i, graphNodes, currentStep, status, flowRunStatus)
      const isActive = sourceStatus === 'completed' || sourceStatus === 'active'
      return {
        id: `${node.name}-${graphNodes[i + 1].name}`,
        source: node.name,
        target: graphNodes[i + 1].name,
        type: 'default',
        animated: sourceStatus === 'active',
        style: {
          stroke: isActive ? '#10b981' : '#d1d5db',
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isActive ? '#10b981' : '#d1d5db',
        },
      }
    })

    return { nodes: rfNodes, edges: rfEdges }
  }, [graphNodes, currentStep, status, flowRunStatus])

  return (
    <div style={{ height }} className="w-full rounded-lg border bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
      >
        <Background gap={16} size={1} color="#f1f5f9" />
      </ReactFlow>
    </div>
  )
}
