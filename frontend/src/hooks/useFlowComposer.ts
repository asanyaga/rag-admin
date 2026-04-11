import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type OnConnect,
  MarkerType,
  Position,
} from '@xyflow/react'
import type {
  AgentTool,
  FlowDefinition,
  FlowDefinitionData,
} from '@/types/agent'
import * as agentApi from '@/api/agent'

/** Unique ID counter for new nodes */
let idCounter = 0
function nextNodeId(): string {
  return `node_${++idCounter}`
}

/** Default edge style */
const EDGE_STYLE = { stroke: '#94a3b8', strokeWidth: 2 }
const EDGE_MARKER = {
  type: MarkerType.ArrowClosed as const,
  color: '#94a3b8',
}

/** Convert a flow definition from the backend into React Flow nodes/edges */
function definitionToReactFlow(
  def: FlowDefinitionData,
  tools: AgentTool[]
): { nodes: Node[]; edges: Edge[] } {
  const toolMap = new Map(tools.map((t) => [t.slug, t]))
  const NODE_SPACING_X = 240
  const NODE_SPACING_Y = 0

  const nodes: Node[] = def.nodes.map((n, i) => {
    const tool = toolMap.get(n.tool)
    return {
      id: n.id,
      type: 'composerNode',
      position: n.position ?? { x: i * NODE_SPACING_X, y: NODE_SPACING_Y },
      data: {
        toolSlug: n.tool,
        label: tool?.name ?? n.tool,
        category: tool?.category ?? 'unknown',
        config: n.config ?? {},
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }
  })

  const edges: Edge[] = def.edges.map((e) => ({
    id: `${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    style: EDGE_STYLE,
    markerEnd: EDGE_MARKER,
  }))

  // Render conditional edges as regular edges for now
  for (const ce of def.conditional_edges ?? []) {
    for (const target of ce.targets) {
      if (target === '__end__') continue
      edges.push({
        id: `${ce.source}-${target}-cond`,
        source: ce.source,
        target,
        style: { ...EDGE_STYLE, strokeDasharray: '6 3' },
        markerEnd: EDGE_MARKER,
        label: ce.router,
      })
    }
  }

  return { nodes, edges }
}

/** Convert React Flow nodes/edges back to a flow definition */
function reactFlowToDefinition(
  nodes: Node[],
  edges: Edge[]
): FlowDefinitionData {
  const flowNodes = nodes.map((n) => ({
    id: n.id,
    tool: n.data.toolSlug as string,
    config: (n.data.config ?? {}) as Record<string, unknown>,
    position: { x: n.position.x, y: n.position.y },
  }))

  const flowEdges = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }))

  return { nodes: flowNodes, edges: flowEdges }
}

export interface UseFlowComposerReturn {
  // Tool catalog
  tools: AgentTool[]
  toolsLoading: boolean

  // React Flow state
  nodes: Node[]
  edges: Edge[]
  onNodesChange: ReturnType<typeof useNodesState>[2]
  onEdgesChange: ReturnType<typeof useEdgesState>[2]
  onConnect: OnConnect

  // Actions
  addNode: (tool: AgentTool, position: { x: number; y: number }) => void
  removeNode: (nodeId: string) => void
  updateNodeConfig: (
    nodeId: string,
    config: Record<string, unknown>
  ) => void

  // Persistence
  flowName: string
  setFlowName: (name: string) => void
  flowDescription: string
  setFlowDescription: (desc: string) => void
  isSaving: boolean
  isLoading: boolean
  savedFlow: FlowDefinition | null
  save: () => Promise<FlowDefinition>
  load: (flowId: string) => Promise<void>

  error: string | null
}

export function useFlowComposer(
  projectId: string | null,
  flowId?: string | null
): UseFlowComposerReturn {
  const [tools, setTools] = useState<AgentTool[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const [flowName, setFlowName] = useState('')
  const [flowDescription, setFlowDescription] = useState('')
  const [savedFlow, setSavedFlow] = useState<FlowDefinition | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toolsRef = useRef<AgentTool[]>([])

  // Fetch available tools
  useEffect(() => {
    let cancelled = false
    setToolsLoading(true)
    agentApi
      .listAgentTools()
      .then((data) => {
        if (!cancelled) {
          setTools(data)
          toolsRef.current = data
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : 'Failed to load tools'
          )
      })
      .finally(() => {
        if (!cancelled) setToolsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Load existing flow if flowId provided
  const load = useCallback(
    async (id: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const flow = await agentApi.getFlowDefinition(id)
        setSavedFlow(flow)
        setFlowName(flow.name)
        setFlowDescription(flow.description ?? '')
        const currentTools =
          toolsRef.current.length > 0 ? toolsRef.current : tools
        const { nodes: n, edges: e } = definitionToReactFlow(
          flow.definition,
          currentTools
        )
        setNodes(n)
        setEdges(e)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load flow'
        )
      } finally {
        setIsLoading(false)
      }
    },
    [tools, setNodes, setEdges]
  )

  useEffect(() => {
    if (flowId && tools.length > 0) {
      load(flowId)
    }
  }, [flowId, tools.length, load])

  // Connect handler
  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => {
        const newEdges = addEdge(connection, eds)
        // Style the newly added edge
        const lastEdge = newEdges[newEdges.length - 1]
        if (lastEdge) {
          lastEdge.style = EDGE_STYLE
          lastEdge.markerEnd = EDGE_MARKER
        }
        return newEdges
      })
    },
    [setEdges]
  )

  // Add a new node from the tool palette
  const addNode = useCallback(
    (tool: AgentTool, position: { x: number; y: number }) => {
      const id = nextNodeId()
      const newNode: Node = {
        id,
        type: 'composerNode',
        position,
        data: {
          toolSlug: tool.slug,
          label: tool.name,
          category: tool.category,
          config: {},
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }
      setNodes((nds) => [...nds, newNode])
    },
    [setNodes]
  )

  // Remove a node and its connected edges
  const removeNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) =>
        eds.filter((e) => e.source !== nodeId && e.target !== nodeId)
      )
    },
    [setNodes, setEdges]
  )

  // Update a node's config
  const updateNodeConfig = useCallback(
    (nodeId: string, config: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, config } } : n
        )
      )
    },
    [setNodes]
  )

  // Save / update
  const save = useCallback(async (): Promise<FlowDefinition> => {
    if (!projectId) throw new Error('No project selected')
    if (!flowName.trim()) throw new Error('Flow name is required')

    setIsSaving(true)
    setError(null)
    try {
      const definition = reactFlowToDefinition(nodes, edges)
      let flow: FlowDefinition

      if (savedFlow) {
        flow = await agentApi.updateFlowDefinition(savedFlow.id, {
          name: flowName,
          description: flowDescription || undefined,
          definition,
        })
      } else {
        flow = await agentApi.createFlowDefinition(projectId, {
          name: flowName,
          description: flowDescription || undefined,
          definition,
        })
      }

      setSavedFlow(flow)
      return flow
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Failed to save flow'
      setError(msg)
      throw err
    } finally {
      setIsSaving(false)
    }
  }, [projectId, flowName, flowDescription, nodes, edges, savedFlow])

  return {
    tools,
    toolsLoading,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    removeNode,
    updateNodeConfig,
    flowName,
    setFlowName,
    flowDescription,
    setFlowDescription,
    isSaving,
    isLoading,
    savedFlow,
    save,
    load,
    error,
  }
}
