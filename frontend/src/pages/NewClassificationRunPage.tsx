// frontend/src/pages/NewClassificationRunPage.tsx
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useParseRuns } from '@/hooks/useParseRuns'
import { ClassificationRunForm } from '@/components/classification/ClassificationRunForm'
import type { ClassificationRunFormValues } from '@/components/classification/ClassificationRunForm'
import { createClassificationRun } from '@/api/classification'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { toast } from 'sonner'
import { formatDistanceToNow } from 'date-fns'
import { ChevronLeft } from 'lucide-react'

type Step = 'document' | 'parse-run' | 'configure'

export default function NewClassificationRunPage(): JSX.Element {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentProject } = useProject()

  const [step, setStep] = useState<Step>('document')
  const [documentSearch, setDocumentSearch] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [selectedParseRunId, setSelectedParseRunId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { documents } = useDocuments(currentProject?.id ?? null)
  const { parseRuns } = useParseRuns(selectedDocumentId)

  const filteredDocuments = documents.filter((d) =>
    d.title.toLowerCase().includes(documentSearch.toLowerCase()),
  )

  const handleDocumentSelect = (id: string) => {
    setSelectedDocumentId(id)
    setSelectedParseRunId(null)
    setStep('parse-run')
  }

  const handleParseRunSelect = (id: string) => {
    setSelectedParseRunId(id)
    setStep('configure')
  }

  const handleSubmit = async (values: ClassificationRunFormValues) => {
    if (!selectedDocumentId || !selectedParseRunId) return
    setIsSubmitting(true)
    try {
      const run = await createClassificationRun(selectedDocumentId, {
        parseRunId: selectedParseRunId,
        labels: values.labels,
        classifierType: values.classifierType,
        classifierConfig: values.classifierConfig,
      })
      toast.success('Classification started')
      navigate(`/classify/${run.id}`)
    } catch (err) {
      toast.error('Failed to start classification', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const selectedDocTitle = documents.find((d) => d.id === selectedDocumentId)?.title

  const completedParseRuns = parseRuns.filter(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/classify')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">New classification run</h1>
      </div>

      {/* Step 1: Select document */}
      <div className={step !== 'document' ? 'opacity-50 pointer-events-none' : ''}>
        <h2 className="text-lg font-medium mb-3">
          {step !== 'document' && selectedDocumentId
            ? `Document: ${selectedDocTitle}`
            : '1. Select document'}
        </h2>
        {step === 'document' && (
          <div className="space-y-3">
            <Input
              placeholder="Search documents…"
              value={documentSearch}
              onChange={(e) => setDocumentSearch(e.target.value)}
            />
            <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
              {filteredDocuments.map((doc) => (
                <button
                  key={doc.id}
                  className="w-full text-left px-4 py-3 hover:bg-muted/50 text-sm"
                  onClick={() => handleDocumentSelect(doc.id)}
                >
                  {doc.title}
                </button>
              ))}
              {filteredDocuments.length === 0 && (
                <p className="px-4 py-3 text-sm text-muted-foreground">No documents found.</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Step 2: Select parse run */}
      {(step === 'parse-run' || step === 'configure') && (
        <div className={step !== 'parse-run' ? 'opacity-50 pointer-events-none' : ''}>
          <h2 className="text-lg font-medium mb-3">
            {step !== 'parse-run' && selectedParseRunId
              ? 'Parse run selected'
              : '2. Select parse run'}
          </h2>
          {step === 'parse-run' && (
            <RadioGroup
              value={selectedParseRunId ?? ''}
              onValueChange={handleParseRunSelect}
              className="space-y-2"
            >
              {completedParseRuns.map((run) => (
                <div key={run.id} className="flex items-center gap-3 border rounded-md px-4 py-3">
                  <RadioGroupItem value={run.id} id={run.id} />
                  <Label htmlFor={run.id} className="flex-1 cursor-pointer">
                    <span className="font-medium">{run.parser}</span>
                    <span className="text-sm text-muted-foreground ml-2">
                      {run.finishedAt
                        ? formatDistanceToNow(new Date(run.finishedAt), { addSuffix: true })
                        : ''}
                    </span>
                  </Label>
                </div>
              ))}
              {completedParseRuns.length === 0 && (
                <Alert>
                  <AlertDescription>No completed parse runs for this document.</AlertDescription>
                </Alert>
              )}
            </RadioGroup>
          )}
        </div>
      )}

      {/* Step 3: Configure */}
      {step === 'configure' && (
        <div>
          <h2 className="text-lg font-medium mb-3">3. Configure labels and model</h2>
          <ClassificationRunForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
        </div>
      )}
    </div>
  )
}
