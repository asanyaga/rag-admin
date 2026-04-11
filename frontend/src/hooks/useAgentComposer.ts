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
  AgentDefinition,
  AgentDefinitionData,
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

/** Convert an agent definition from the backend into React Flow nodes/edges */
function definitionToReactFlow(
  def: AgentDefinitionData,
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

/** Convert React Flow nodes/edges back to an agent definition */
function reactFlowToDefinition(
  nodes: Node[],
  edges: Edge[]
): AgentDefinitionData {
  const agentNodes = nodes.map((n) => ({
    id: n.id,
    tool: n.data.toolSlug as string,
    config: (n.data.config ?? {}) as Record<string, unknown>,
    position: { x: n.position.x, y: n.position.y },
  }))

  const agentEdges = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }))

  return { nodes: agentNodes, edges: agentEdges }
}

export interface UseAgentComposerReturn {
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
  agentName: string
  setAgentName: (name: string) => void
  agentDescription: string
  setAgentDescription: (desc: string) => void
  isSaving: boolean
  isLoading: boolean
  savedAgent: AgentDefinition | null
  save: () => Promise<AgentDefinition>
  load: (agentId: string) => Promise<void>

  error: string | null
}

export function useAgentComposer(
  projectId: string | null,
  agentId?: string | null
): UseAgentComposerReturn {
  const [tools, setTools] = useState<AgentTool[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [savedAgent, setSavedAgent] = useState<AgentDefinition | null>(null)
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

  // Load existing agent if agentId provided
  const load = useCallback(
    async (id: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const agent = await agentApi.getAgentDefinition(id)
        setSavedAgent(agent)
        setAgentName(agent.name)
        setAgentDescription(agent.description ?? '')
        const currentTools =
          toolsRef.current.length > 0 ? toolsRef.current : tools
        const { nodes: n, edges: e } = definitionToReactFlow(
          agent.definition,
          currentTools
        )
        setNodes(n)
        setEdges(e)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load agent'
        )
      } finally {
        setIsLoading(false)
      }
    },
    [tools, setNodes, setEdges]
  )

  useEffect(() => {
    if (agentId && tools.length > 0) {
      load(agentId)
    }
  }, [agentId, tools.length, load])

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
  const save = useCallback(async (): Promise<AgentDefinition> => {
    if (!projectId) throw new Error('No project selected')
    if (!agentName.trim()) throw new Error('Agent name is required')

    setIsSaving(true)
    setError(null)
    try {
      const definition = reactFlowToDefinition(nodes, edges)
      let agent: AgentDefinition

      if (savedAgent) {
        agent = await agentApi.updateAgentDefinition(savedAgent.id, {
          name: agentName,
          description: agentDescription || undefined,
          definition,
        })
      } else {
        agent = await agentApi.createAgentDefinition(projectId, {
          name: agentName,
          description: agentDescription || undefined,
          definition,
        })
      }

      setSavedAgent(agent)
      return agent
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Failed to save agent'
      setError(msg)
      throw err
    } finally {
      setIsSaving(false)
    }
  }, [projectId, agentName, agentDescription, nodes, edges, savedAgent])

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
    agentName,
    setAgentName,
    agentDescription,
    setAgentDescription,
    isSaving,
    isLoading,
    savedAgent,
    save,
    load,
    error,
  }
}
