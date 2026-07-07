import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { ParseMethodSelector, PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'
import { CaseDetailView } from '@/components/parser-eval/CaseDetailView'

const DEFAULT_ADAPTER = 'docling'

export default function ParserEvalCasePage(): JSX.Element {
  const { caseId } = useParams<{ caseId: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const navigate = useNavigate()

  if (caseId) return <CaseDetailView projectId={projectId} caseId={caseId} />

  return <NewCaseForm projectId={projectId} onDone={(id) => navigate(`/evaluation/parser/cases/${id}`)} />
}

function NewCaseForm({ projectId, onDone }: { projectId: string | null; onDone: (id: string) => void }) {
  const { sourceDocuments } = useSourceDocuments()
  const { createCase, bootstrapTableCase } = useParserEvalCases(projectId)
  const [dimension, setDimension] = useState<'text' | 'table'>('text')
  const [sourceDocumentId, setSourceDocumentId] = useState('')
  const [pages, setPages] = useState<string[]>([''])
  const [adapter, setAdapter] = useState(DEFAULT_ADAPTER)
  const [config, setConfig] = useState<ParseConfig>(PARSER_REGISTRY[DEFAULT_ADAPTER]?.defaultConfig ?? {})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = dimension === 'text'
    ? sourceDocumentId !== '' && pages.some((p) => p.trim() !== '')
    : sourceDocumentId !== ''

  const handleSubmit = async () => {
    setSubmitting(true); setError(null)
    try {
      if (dimension === 'text') {
        const created = await createCase({ sourceDocumentId, dimension: 'text', expected: { pages } })
        onDone(created.id)
      } else {
        const created = await bootstrapTableCase({ sourceDocumentId, adapter, config })
        onDone(created.id)
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setError(status === 409 ? `A ${dimension} case already exists for this document.`
        : status === 400 ? 'The chosen parser could not parse this document.'
        : 'Failed to save case.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <button onClick={() => history.back()}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back
      </button>
      <h1 className="text-2xl font-bold">New case</h1>

      <div>
        <Label>Source document</Label>
        <Select value={sourceDocumentId} onValueChange={setSourceDocumentId}>
          <SelectTrigger><SelectValue placeholder="Select a document" /></SelectTrigger>
          <SelectContent>
            {sourceDocuments.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.filename ?? d.id}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label>Dimension</Label>
        <Select value={dimension} onValueChange={(v) => setDimension(v as 'text' | 'table')}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="text">Text faithfulness</SelectItem>
            <SelectItem value="table">Table extraction</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {dimension === 'text' ? (
        <div className="space-y-2">
          <Label>Ground truth (per page)</Label>
          {pages.map((page, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Page {i + 1}</span>
                {pages.length > 1 && (
                  <Button variant="ghost" size="sm"
                    onClick={() => setPages((p) => p.filter((_, idx) => idx !== i))}>Remove</Button>
                )}
              </div>
              <Textarea value={page} rows={4}
                onChange={(e) => setPages((p) => p.map((v, idx) => (idx === i ? e.target.value : v)))}
                placeholder={`Correct readable text for page ${i + 1}`} />
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setPages((p) => [...p, ''])}>Add page</Button>
        </div>
      ) : (
        <div className="space-y-2">
          <Label>Bootstrap ground truth from a trusted parser</Label>
          <p className="text-xs text-muted-foreground">
            Run a parser you trust; its extracted tables become a draft you review next.
          </p>
          <div className="rounded-md border p-3">
            <ParseMethodSelector
              compact
              parserType={adapter}
              config={config}
              onParserTypeChange={setAdapter}
              onConfigChange={setConfig}
            />
          </div>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
        {submitting ? 'Saving…' : dimension === 'table' ? 'Bootstrap draft' : 'Create case'}
      </Button>
    </div>
  )
}
