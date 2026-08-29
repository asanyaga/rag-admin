import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Play } from 'lucide-react'
import { toast } from 'sonner'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { startAgentRun } from '@/api/agent'
import { deriveRunFormFields, validateGraph, type UnmetInput } from '@/lib/agentGraph'
import type { AgentTool, AgentToolRuntimeInput, AgentDefinitionData } from '@/types/agent'
import type { SourceDocument } from '@/types/sourceDocument'
import type { DocumentListItem } from '@/types/document'
import type { ExtractionSchema } from '@/types/extraction'

interface Props {
  projectId: string
  definitionId: string
  definition: AgentDefinitionData
  tools: AgentTool[]
  onStarted: (runId: string) => void
}

/** Best-effort human label for an unmet upstream input: the producing tool's
 *  own runtimeInput label for that key, falling back to the raw key. */
function labelFor(unmet: UnmetInput, tools: AgentTool[]): string {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  for (const t of bySlug.values()) {
    const input = t.runtimeInputs.find((f) => f.key === unmet.key)
    if (input) return input.label
  }
  return unmet.key
}

interface PickerData {
  sourceDocuments: SourceDocument[]
  readyDocuments: DocumentListItem[]
  schemas: ExtractionSchema[]
}

function renderPicker(
  field: AgentToolRuntimeInput,
  data: PickerData,
  value: string,
  onChange: (v: string) => void,
) {
  const selectClass = 'w-full rounded-md border border-input bg-background px-3 py-2 text-sm'

  if (field.widget === 'source_document_picker') {
    return (
      <select id={field.key} aria-label={field.label} className={selectClass}
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a document...</option>
        {data.sourceDocuments.map((sd) => (
          <option key={sd.id} value={sd.id}>{sd.filename ?? sd.id}</option>
        ))}
      </select>
    )
  }

  if (field.widget === 'document_picker') {
    return (
      <select id={field.key} aria-label={field.label} className={selectClass}
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a document...</option>
        {data.readyDocuments.map((doc) => (
          <option key={doc.id} value={doc.id}>{doc.title}</option>
        ))}
      </select>
    )
  }

  if (field.widget === 'extraction_schema_picker') {
    return (
      <select id={field.key} aria-label={field.label} className={selectClass}
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a schema...</option>
        {data.schemas.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>
    )
  }

  return <span className="text-xs text-muted-foreground">Unsupported input: {field.widget}</span>
}

export function AgentRunForm({ projectId, definitionId, definition, tools, onStarted }: Props) {
  const fields = useMemo(() => deriveRunFormFields(definition.nodes, tools), [definition, tools])
  const unmet = useMemo(
    () => validateGraph(definition.nodes, definition.edges ?? [], tools),
    [definition, tools],
  )
  const { sourceDocuments } = useSourceDocuments()
  const { documents } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)
  const readyDocuments = documents.filter((d) => d.status === 'ready')
  const [values, setValues] = useState<Record<string, string>>({})
  const [isStarting, setStarting] = useState(false)

  const graphValid = unmet.length === 0
  const ready = graphValid && fields.every((f) => values[f.key])

  const set = (key: string, v: string) => setValues((prev) => ({ ...prev, [key]: v }))

  const handleRun = async () => {
    setStarting(true)
    try {
      const run = await startAgentRun(projectId, {
        agentDefinitionId: definitionId, initialState: { ...values },
      })
      onStarted(run.id)
    } catch (err) {
      toast.error('Failed to start run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    } finally { setStarting(false) }
  }

  return (
    <div className="space-y-3">
      {!graphValid && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          This agent can't run yet: {unmet.map((u) => `node "${u.nodeId}" needs ${labelFor(u, tools)}`).join('; ')}.
        </div>
      )}
      {fields.map((f) => (
        <div key={f.key} className="space-y-1.5">
          <Label htmlFor={f.key} className="text-xs">{f.label}</Label>
          {renderPicker(f, { sourceDocuments, readyDocuments, schemas }, values[f.key] ?? '', (v) => set(f.key, v))}
        </div>
      ))}
      <Button size="sm" disabled={!ready || isStarting} onClick={handleRun}>
        <Play className="h-4 w-4 mr-1.5" />{isStarting ? 'Starting...' : 'Run'}
      </Button>
    </div>
  )
}
