import { useCallback, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type ReactFlowInstance,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { ToolPalette } from './ToolPalette'
import { ComposerNode } from './ComposerNode'
import { NodeConfigPanel } from './NodeConfigPanel'
import { validateGraph } from '@/lib/agentGraph'
import type { AgentTool } from '@/types/agent'
import type { UseAgentComposerReturn } from '@/hooks/useAgentComposer'

const nodeTypes = { composerNode: ComposerNode }

interface AgentComposerProps {
  composer: UseAgentComposerReturn
}

export function AgentComposer({ composer }: AgentComposerProps) {
  const navigate = useNavigate()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const {
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
    save,
    savedAgent,
  } = composer

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId]
  )

  // Per-node unmet upstream inputs (human labels), computed from the current canvas
  const unmetByNode = useMemo(() => {
    const gnodes = nodes.map((n) => ({ id: n.id, tool: n.data.toolSlug as string }))
    const gedges = edges.map((e) => ({ source: e.source, target: e.target }))
    const bySlug = new Map(tools.map((t) => [t.slug, t]))
    const map: Record<string, string[]> = {}
    for (const u of validateGraph(gnodes, gedges, tools)) {
      const tool = bySlug.get(nodes.find((n) => n.id === u.nodeId)?.data.toolSlug as string)
      const label = tool?.runtimeInputs.find((f) => f.key === u.key)?.label ?? u.key
      ;(map[u.nodeId] ??= []).push(label)
    }
    return map
  }, [nodes, edges, tools])

  // Inject callbacks into node data so ComposerNode can call them
  const nodesWithCallbacks: Node[] = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        selected: n.id === selectedNodeId,
        data: {
          ...n.data,
          onRemove: removeNode,
          onSelect: setSelectedNodeId,
          unmetInputs: unmetByNode[n.id] ?? [],
        },
      })),
    [nodes, selectedNodeId, removeNode, unmetByNode]
  )

  // Handle drop from tool palette
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const toolJson = e.dataTransfer.getData('application/agent-tool')
      if (!toolJson || !reactFlowInstance || !reactFlowWrapper.current) return

      const tool: AgentTool = JSON.parse(toolJson)
      const bounds = reactFlowWrapper.current.getBoundingClientRect()
      const position = reactFlowInstance.screenToFlowPosition({
        x: e.clientX - bounds.left,
        y: e.clientY - bounds.top,
      })

      addNode(tool, position)
    },
    [reactFlowInstance, addNode]
  )

  const handleSave = async () => {
    try {
      const saved = await save()
      toast.success(savedAgent ? 'Agent updated' : 'Agent created')
      if (!savedAgent) {
        navigate(`/agent/${saved.id}/runs`, { replace: true })
      }
    } catch (err) {
      toast.error('Failed to save agent', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  return (
    <div className="-m-6 flex h-[calc(100vh-3rem)] flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b bg-white px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => navigate('/agent')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <Separator orientation="vertical" className="h-6" />
        <Input
          className="h-8 w-56 text-sm font-medium"
          placeholder="Agent name..."
          value={agentName}
          onChange={(e) => setAgentName(e.target.value)}
        />
        <Input
          className="h-8 w-72 text-sm"
          placeholder="Description (optional)"
          value={agentDescription}
          onChange={(e) => setAgentDescription(e.target.value)}
        />
        <div className="ml-auto">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving || !agentName.trim() || nodes.length === 0}
          >
            <Save className="h-4 w-4 mr-1.5" />
            {isSaving ? 'Saving...' : savedAgent ? 'Update' : 'Save'}
          </Button>
        </div>
      </div>

      {/* Main area: palette | canvas | config */}
      <div className="flex flex-1 overflow-hidden">
        {/* Tool palette */}
        <div className="w-48 shrink-0 overflow-y-auto border-r bg-gray-50/50">
          <ToolPalette tools={tools} isLoading={toolsLoading} />
        </div>

        {/* Canvas */}
        <div className="flex-1" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodesWithCallbacks}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.5 }}
            proOptions={{ hideAttribution: true }}
            deleteKeyCode={['Backspace', 'Delete']}
            snapToGrid
            snapGrid={[16, 16]}
          >
            <Background gap={16} size={1} color="#e2e8f0" />
            <Controls showInteractive={false} />
            <MiniMap
              nodeStrokeWidth={2}
              nodeColor={(n) => {
                const cat = n.data?.category as string
                const colors: Record<string, string> = {
                  extraction: '#93c5fd',
                  control: '#fcd34d',
                  export: '#6ee7b7',
                  indexing: '#c4b5fd',
                  trigger: '#fdba74',
                }
                return colors[cat] ?? '#d1d5db'
              }}
              maskColor="rgba(0,0,0,0.08)"
            />
          </ReactFlow>
        </div>

        {/* Config panel */}
        {selectedNode && (
          <div className="w-64 shrink-0 overflow-y-auto border-l bg-white">
            <NodeConfigPanel
              node={selectedNode}
              tools={tools}
              onUpdateConfig={updateNodeConfig}
              onClose={() => setSelectedNodeId(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
