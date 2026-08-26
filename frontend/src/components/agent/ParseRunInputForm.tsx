import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Play } from 'lucide-react'
import type { SourceDocument } from '@/types/sourceDocument'
import type { StartParseRunRequest } from '@/types/agent'

const PARSERS = ['simple', 'llamaparse', 'landing_ai', 'docling'] as const

interface ParseRunInputFormProps {
  agentDefinitionId: string
  sourceDocuments: SourceDocument[]
  isStarting: boolean
  onStart: (request: StartParseRunRequest) => Promise<void>
}

export function ParseRunInputForm({
  agentDefinitionId,
  sourceDocuments,
  isStarting,
  onStart,
}: ParseRunInputFormProps) {
  const [sourceDocumentId, setSourceDocumentId] = useState('')
  const [parser, setParser] = useState<string>('simple')
  const [representationKind, setRepresentationKind] = useState('extract_rich')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sourceDocumentId) return
    await onStart({
      agentDefinitionId,
      sourceDocumentId,
      parser,
      representationKind,
    })
    setSourceDocumentId('')
    setParser('simple')
    setRepresentationKind('extract_rich')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label className="text-xs">Source Document</Label>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={sourceDocumentId}
            onChange={(e) => setSourceDocumentId(e.target.value)}
          >
            <option value="">Select a source document...</option>
            {sourceDocuments.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Parser</Label>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={parser}
            onChange={(e) => setParser(e.target.value)}
          >
            {PARSERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Representation Kind</Label>
          <Input
            className="text-sm"
            value={representationKind}
            onChange={(e) => setRepresentationKind(e.target.value)}
          />
        </div>
      </div>
      <Button type="submit" size="sm" disabled={!sourceDocumentId || isStarting}>
        <Play className="h-4 w-4 mr-1.5" />
        {isStarting ? 'Starting...' : 'Run'}
      </Button>
    </form>
  )
}
