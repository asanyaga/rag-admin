import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2 } from 'lucide-react'
import type { DocumentListItem } from '@/types/document'
import type { ExtractionSchema } from '@/types/extraction'
import type { StartProcessingRequest } from '@/types/agent'

interface ReceiptProcessFormProps {
  documents: DocumentListItem[]
  schemas: ExtractionSchema[]
  isProcessing: boolean
  onProcess: (request: StartProcessingRequest) => Promise<void>
}

export function ReceiptProcessForm({
  documents,
  schemas,
  isProcessing,
  onProcess,
}: ReceiptProcessFormProps) {
  const [documentId, setDocumentId] = useState<string>('')
  const [schemaId, setSchemaId] = useState<string>('')

  const readyDocuments = documents.filter((d) => d.status === 'ready')
  const canSubmit = documentId && schemaId && !isProcessing

  const handleSubmit = async () => {
    if (!canSubmit) return
    await onProcess({
      documentId,
      extractionSchemaId: schemaId,
    })
    setDocumentId('')
    setSchemaId('')
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Document</label>
          <Select value={documentId} onValueChange={setDocumentId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a document..." />
            </SelectTrigger>
            <SelectContent>
              {readyDocuments.map((doc) => (
                <SelectItem key={doc.id} value={doc.id}>
                  {doc.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Extraction Schema</label>
          <Select value={schemaId} onValueChange={setSchemaId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a schema..." />
            </SelectTrigger>
            <SelectContent>
              {schemas.map((schema) => (
                <SelectItem key={schema.id} value={schema.id}>
                  {schema.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button onClick={handleSubmit} disabled={!canSubmit} size="sm">
        {isProcessing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Process Receipt
      </Button>
    </div>
  )
}
