import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Loader2,
  Sparkles,
  FileText,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Badge } from '@/components/ui/badge'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useGoldenSetDetail } from '@/hooks/useGoldenSets'
import type { QuestionType, GenerateRequest } from '@/types/golden-set'

const LLM_MODELS = [
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
]

const QUESTION_TYPES: { value: QuestionType; label: string; description: string }[] = [
  { value: 'factual', label: 'Factual', description: 'Direct fact-based questions' },
  { value: 'comparison', label: 'Comparison', description: 'Compare concepts or data points' },
  { value: 'summarization', label: 'Summarization', description: 'Summarize sections or topics' },
]

const QUERIES_OPTIONS = [3, 5, 10, 15]

export default function GoldenSetGeneratePage() {
  const { goldenSetId } = useParams<{ goldenSetId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { documents } = useDocuments(projectId, 'ready' as never)
  const {
    goldenSet,
    isLoading,
    isGenerating,
    generationProgress,
    triggerGeneration,
  } = useGoldenSetDetail(projectId, goldenSetId ?? null)

  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set())
  const [model, setModel] = useState('gpt-4o')
  const [queriesPerDoc, setQueriesPerDoc] = useState(5)
  const [questionTypes, setQuestionTypes] = useState<Set<QuestionType>>(new Set(['factual']))
  const [temperature, setTemperature] = useState(0.7)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Filter to only "ready" documents
  const readyDocs = useMemo(
    () => documents.filter((d) => d.status === 'ready'),
    [documents]
  )

  const toggleDoc = (docId: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  const toggleQuestionType = (qt: QuestionType) => {
    setQuestionTypes((prev) => {
      const next = new Set(prev)
      if (next.has(qt)) {
        if (next.size > 1) next.delete(qt) // Keep at least one
      } else {
        next.add(qt)
      }
      return next
    })
  }

  const canSubmit = selectedDocIds.size > 0 && questionTypes.size > 0 && !isSubmitting

  const handleGenerate = async () => {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const data: GenerateRequest = {
        documentIds: Array.from(selectedDocIds),
        llmProvider: 'openai',
        llmModel: model,
        queriesPerDocument: queriesPerDoc,
        questionTypes: Array.from(questionTypes),
        temperature,
      }
      await triggerGeneration(data)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start generation')
      setIsSubmitting(false)
    }
  }

  // Generation completed — navigate to editor
  const generationDone =
    goldenSet?.generationStatus === 'completed' || goldenSet?.generationStatus === 'failed'
  const generationCompleted = goldenSet?.generationStatus === 'completed'
  const generationFailed = goldenSet?.generationStatus === 'failed'

  if (isLoading || !goldenSet) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Show progress view when generating
  if (isGenerating) {
    const progress = generationProgress
    const pct = progress && progress.totalWindows > 0
      ? Math.round((progress.completedWindows / progress.totalWindows) * 100)
      : 0

    return (
      <div className="max-w-lg mx-auto py-16 space-y-6">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary/10">
            <Sparkles className="h-6 w-6 text-primary animate-pulse" />
          </div>
          <h2 className="text-xl font-semibold">Generating Queries</h2>
          <p className="text-sm text-muted-foreground">
            Processing document windows with AI...
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>{progress?.completedWindows ?? 0} / {progress?.totalWindows ?? '?'} windows</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    )
  }

  // Show completion/failure view
  if (generationDone && isSubmitting) {
    return (
      <div className="max-w-lg mx-auto py-16 space-y-6">
        <div className="text-center space-y-3">
          {generationCompleted ? (
            <>
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/10">
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              </div>
              <h2 className="text-xl font-semibold">Generation Complete</h2>
              <p className="text-sm text-muted-foreground">
                {goldenSet.queryCount} queries generated. Review and curate them now.
              </p>
              {generationProgress?.errorMessage && (
                <p className="text-sm text-amber-600">{generationProgress.errorMessage}</p>
              )}
            </>
          ) : (
            <>
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-destructive/10">
                <AlertCircle className="h-6 w-6 text-destructive" />
              </div>
              <h2 className="text-xl font-semibold">Generation Failed</h2>
              <p className="text-sm text-muted-foreground">
                {generationProgress?.errorMessage || 'An error occurred during generation.'}
              </p>
            </>
          )}

          <div className="flex gap-3 justify-center pt-4">
            {generationCompleted && (
              <Button onClick={() => navigate(`/evaluation/golden-sets/${goldenSetId}`)}>
                Review Queries
              </Button>
            )}
            {generationFailed && (
              <Button variant="outline" onClick={() => setIsSubmitting(false)}>
                Try Again
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => navigate(`/evaluation/golden-sets/${goldenSetId}`)}
            >
              Go to Editor
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Config form
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(`/evaluation/golden-sets/${goldenSetId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Auto-Generate Queries</h1>
          <p className="text-sm text-muted-foreground">{goldenSet.name}</p>
        </div>
      </div>

      {/* Document selection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Select Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {readyDocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No documents with "ready" status found. Upload and process documents first.
            </p>
          ) : (
            <div className="space-y-2">
              {readyDocs.map((doc) => (
                <label
                  key={doc.id}
                  className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <Checkbox
                    checked={selectedDocIds.has(doc.id)}
                    onCheckedChange={() => toggleDoc(doc.id)}
                  />
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm font-medium truncate">{doc.title}</span>
                </label>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configuration */}
      <div className="grid grid-cols-2 gap-6">
        {/* LLM Model */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">LLM Model</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LLM_MODELS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Queries per document */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Queries per Document</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              {QUERIES_OPTIONS.map((n) => (
                <Button
                  key={n}
                  size="sm"
                  variant={queriesPerDoc === n ? 'default' : 'outline'}
                  onClick={() => setQueriesPerDoc(n)}
                >
                  {n}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Question types */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Question Types</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {QUESTION_TYPES.map((qt) => (
                <label
                  key={qt.value}
                  className="flex items-center gap-3 cursor-pointer"
                >
                  <Checkbox
                    checked={questionTypes.has(qt.value)}
                    onCheckedChange={() => toggleQuestionType(qt.value)}
                  />
                  <div>
                    <span className="text-sm font-medium">{qt.label}</span>
                    <p className="text-xs text-muted-foreground">{qt.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Temperature */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Temperature</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Slider
              value={[temperature]}
              onValueChange={([v]) => setTemperature(v)}
              min={0}
              max={1.5}
              step={0.1}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Precise (0)</span>
              <Badge variant="secondary">{temperature.toFixed(1)}</Badge>
              <span>Creative (1.5)</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Submit */}
      {submitError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
          {submitError}
        </div>
      )}

      <div className="flex justify-end gap-3">
        <Button
          variant="outline"
          onClick={() => navigate(`/evaluation/golden-sets/${goldenSetId}`)}
        >
          Cancel
        </Button>
        <Button onClick={handleGenerate} disabled={!canSubmit}>
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              Generate Queries
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
