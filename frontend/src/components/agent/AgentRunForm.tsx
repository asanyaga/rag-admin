import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Play } from 'lucide-react'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { startAgentRun } from '@/api/agent'
import type { AgentTool, AgentDefinitionData } from '@/types/agent'

interface Props {
  projectId: string
  definitionId: string
  definition: AgentDefinitionData
  tools: AgentTool[]
  onStarted: (runId: string) => void
}

/** form fields = ⋃ runtime_inputs − ⋃ outputs across the graph's tools */
function deriveFields(definition: AgentDefinitionData, tools: AgentTool[]) {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const used = definition.nodes.map((n) => bySlug.get(n.tool)).filter(Boolean) as AgentTool[]
  const produced = new Set(used.flatMap((t) => t.outputs))
  const seen = new Set<string>()
  const fields = []
  for (const t of used)
    for (const f of t.runtimeInputs)
      if (!produced.has(f.key) && !seen.has(f.key)) { seen.add(f.key); fields.push(f) }
  return fields
}

export function AgentRunForm({ projectId, definitionId, definition, tools, onStarted }: Props) {
  const fields = useMemo(() => deriveFields(definition, tools), [definition, tools])
  const { sourceDocuments } = useSourceDocuments()
  const [values, setValues] = useState<Record<string, string>>({})
  const [isStarting, setStarting] = useState(false)

  const ready = fields.every((f) => values[f.key])

  const handleRun = async () => {
    setStarting(true)
    try {
      const run = await startAgentRun(projectId, {
        agentDefinitionId: definitionId, initialState: { ...values },
      })
      onStarted(run.id)
    } finally { setStarting(false) }
  }

  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-1.5">
          <Label htmlFor={f.key} className="text-xs">{f.label}</Label>
          {f.widget === 'source_document_picker' ? (
            <select id={f.key} aria-label={f.label}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={values[f.key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}>
              <option value="">Select a document...</option>
              {sourceDocuments.map((sd) => (
                <option key={sd.id} value={sd.id}>{sd.filename ?? sd.id}</option>
              ))}
            </select>
          ) : (
            <span className="text-xs text-muted-foreground">Unsupported input: {f.widget}</span>
          )}
        </div>
      ))}
      <Button size="sm" disabled={!ready || isStarting} onClick={handleRun}>
        <Play className="h-4 w-4 mr-1.5" />{isStarting ? 'Starting...' : 'Run'}
      </Button>
    </div>
  )
}
