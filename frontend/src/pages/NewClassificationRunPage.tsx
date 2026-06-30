import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link, useLocation } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { ClassificationConfig } from '@/components/classification/ClassificationConfig'
import type { ClassificationConfigValue } from '@/components/classification/ClassificationConfig'
import { useParseRuns } from '@/hooks/useParseRuns'
import { createClassificationRun } from '@/api/classification'
import type { ParseConfig } from '@/types/parsing'
import type { RerunDefaults } from '@/types/classification'

export function NewClassificationRunPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()

  const documentId = searchParams.get('documentId') ?? ''
  const defaults = (location.state as { defaults?: RerunDefaults; documentTitle?: string } | null)
    ?.defaults
  const documentTitle = (location.state as { documentTitle?: string } | null)?.documentTitle

  const { parseRuns } = useParseRuns(documentId || null)

  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )

  const [parserType, setParserType] = useState('simple')
  const [parserConfig, setParserConfig] = useState<ParseConfig>({})
  const [classifyConfig, setClassifyConfig] = useState<ClassificationConfigValue>({
    labels: defaults?.labels ?? [],
    classifierType: defaults?.classifierType ?? 'llm',
    classifierConfig: defaults?.classifierConfig ?? {},
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Seed parse config from the latest successful parse run
  useEffect(() => {
    if (!latestViableRun) return
    setParserType(latestViableRun.parser ?? 'simple')
    const cfg = { ...(latestViableRun.config as Record<string, unknown> ?? {}) }
    delete cfg['parser']
    setParserConfig(cfg as ParseConfig)
  }, [latestViableRun?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const backHref = `/classify${documentId ? `?documentId=${documentId}` : ''}`

  const handleSubmit = async () => {
    if (!documentId || classifyConfig.labels.length === 0) return
    if (!latestViableRun) {
      setError('No completed parse run found for this document. Parse it first.')
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      const run = await createClassificationRun(documentId, {
        parseRunId: latestViableRun.id,
        labels: classifyConfig.labels,
        classifierType: classifyConfig.classifierType,
        classifierConfig: classifyConfig.classifierConfig,
      })
      navigate(`/classify/${run.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start classification')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-6 space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to={backHref}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Link>
      </Button>

      <div>
        <h1 className="text-2xl font-semibold">New classification run</h1>
        {documentTitle && (
          <p className="text-sm text-muted-foreground mt-1">{documentTitle}</p>
        )}
      </div>

      <ParseMethodSelector
        parserType={parserType}
        config={parserConfig}
        onParserTypeChange={setParserType}
        onConfigChange={setParserConfig}
        disabled={isSubmitting}
      />

      <Separator />

      <ClassificationConfig
        defaultValues={{
          labels: classifyConfig.labels,
          classifierType: classifyConfig.classifierType,
          classifierConfig: classifyConfig.classifierConfig,
        }}
        onChange={setClassifyConfig}
      />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleSubmit}
          disabled={classifyConfig.labels.length === 0 || isSubmitting}
        >
          {isSubmitting ? 'Starting…' : 'Start classification'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={backHref}>Cancel</Link>
        </Button>
      </div>
    </div>
  )
}
