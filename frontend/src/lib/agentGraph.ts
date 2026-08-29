import type { AgentTool, AgentToolRuntimeInput } from '@/types/agent'

export interface GraphNode { id: string; tool: string }
export interface GraphEdge { source: string; target: string }
export interface UnmetInput { nodeId: string; key: string }

const SYNTHETIC = new Set(['__start__', '__end__'])

function reachablePredecessors(nodeId: string, preds: Map<string, Set<string>>): Set<string> {
  const seen = new Set<string>()
  const stack = [...(preds.get(nodeId) ?? [])]
  while (stack.length) {
    const p = stack.pop() as string
    if (seen.has(p)) continue
    seen.add(p)
    for (const q of preds.get(p) ?? []) stack.push(q)
  }
  return seen
}

/** Mirror of backend validate_graph: an `upstream` input is unmet unless a
 *  reachable predecessor produces its key. */
export function validateGraph(nodes: GraphNode[], edges: GraphEdge[], tools: AgentTool[]): UnmetInput[] {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const preds = new Map<string, Set<string>>(nodes.map((n) => [n.id, new Set<string>()]))
  for (const e of edges) {
    if (SYNTHETIC.has(e.source) || SYNTHETIC.has(e.target)) continue
    if (!preds.has(e.target)) preds.set(e.target, new Set())
    preds.get(e.target)!.add(e.source)
  }
  const outputsOf = (id: string): Set<string> => {
    const n = nodes.find((x) => x.id === id)
    const t = n && bySlug.get(n.tool)
    return new Set(t ? t.outputs : [])
  }
  const unmet: UnmetInput[] = []
  for (const n of nodes) {
    const t = bySlug.get(n.tool)
    if (!t) continue
    const upstreamKeys = new Set<string>()
    for (const p of reachablePredecessors(n.id, preds))
      for (const k of outputsOf(p)) upstreamKeys.add(k)
    for (const f of t.runtimeInputs)
      if (f.source === 'upstream' && !upstreamKeys.has(f.key))
        unmet.push({ nodeId: n.id, key: f.key })
  }
  return unmet
}

/** Run-form fields = form/either inputs not produced by any used node, deduped. */
export function deriveRunFormFields(nodes: GraphNode[], tools: AgentTool[]): AgentToolRuntimeInput[] {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const used = nodes.map((n) => bySlug.get(n.tool)).filter(Boolean) as AgentTool[]
  const produced = new Set(used.flatMap((t) => t.outputs))
  const seen = new Set<string>()
  const fields: AgentToolRuntimeInput[] = []
  for (const t of used)
    for (const f of t.runtimeInputs)
      if (f.source !== 'upstream' && !produced.has(f.key) && !seen.has(f.key)) {
        seen.add(f.key); fields.push(f)
      }
  return fields
}
