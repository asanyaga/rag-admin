import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Play } from 'lucide-react'
import type { DocumentListItem } from '@/types/document'
import type { ExtractionSchema } from '@/types/extraction'
import type { StartExtractRunRequest } from '@/types/agent'

interface FlowRunInputFormProps {
  flowDefinitionId: string
  documents: DocumentListItem[]
  schemas: ExtractionSchema[]
  isStarting: boolean
  onStart: (request: StartExtractRunRequest) => Promise<void>
}

export function FlowRunInputForm({
  flowDefinitionId,
  documents,
  schemas,
  isStarting,
  onStart,
}: FlowRunInputFormProps) {
  const [documentId, setDocumentId] = useState('')
  const [schemaId, setSchemaId] = useState('')

  const readyDocuments = documents.filter((d) => d.status === 'ready')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!documentId || !schemaId) return
    await onStart({
      flowDefinitionId,
      documentId,
      extractionSchemaId: schemaId,
    })
    setDocumentId('')
    setSchemaId('')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="text-xs">Document</Label>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
          >
            <option value="">Select a document...</option>
            {readyDocuments.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.title}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Extraction Schema</Label>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={schemaId}
            onChange={(e) => setSchemaId(e.target.value)}
          >
            <option value="">Select a schema...</option>
            {schemas.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Button
        type="submit"
        size="sm"
        disabled={!documentId || !schemaId || isStarting}
      >
        <Play className="h-4 w-4 mr-1.5" />
        {isStarting ? 'Starting...' : 'Run'}
      </Button>
    </form>
  )
}
