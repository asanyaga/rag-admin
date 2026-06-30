import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { ClassificationConfig } from './ClassificationConfig'
import type { ClassificationConfigValue } from './ClassificationConfig'
import type { RerunDefaults } from './ClassificationRunDetail'
import { useParseRuns } from '@/hooks/useParseRuns'
import { createClassificationRun } from '@/api/classification'
import type { ParseConfig } from '@/types/parsing'

interface ClassificationRunSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  documentId: string
  documentTitle: string
  defaultValues?: RerunDefaults
  onStarted: (runId: string) => void
}

export function ClassificationRunSheet({
  open,
  onOpenChange,
  documentId,
  documentTitle,
  defaultValues,
  onStarted,
}: ClassificationRunSheetProps) {
  const { parseRuns } = useParseRuns(open ? documentId : null)

  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )

  const [parserType, setParserType] = useState('simple')
  const [parserConfig, setParserConfig] = useState<ParseConfig>({})
  const [classifyConfig, setClassifyConfig] = useState<ClassificationConfigValue>({
    labels: defaultValues?.labels ?? [],
    classifierType: defaultValues?.classifierType ?? 'llm',
    classifierConfig: defaultValues?.classifierConfig ?? {},
  })
  const [configKey, setConfigKey] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset all form state each time the sheet opens
  useEffect(() => {
    if (!open) return
    setConfigKey((k) => k + 1)
    setClassifyConfig({
      labels: defaultValues?.labels ?? [],
      classifierType: defaultValues?.classifierType ?? 'llm',
      classifierConfig: defaultValues?.classifierConfig ?? {},
    })
    setError(null)
    setIsSubmitting(false)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Seed parse config from latest viable run when it loads
  useEffect(() => {
    if (!latestViableRun) return
    setParserType(latestViableRun.parser ?? 'simple')
    const cfg = { ...(latestViableRun.config as Record<string, unknown> ?? {}) }
    delete cfg['parser']
    setParserConfig(cfg as ParseConfig)
  }, [latestViableRun?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = async () => {
    if (classifyConfig.labels.length === 0) return
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
      toast.success('Classification started')
      onStarted(run.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start classification')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[60vw] max-w-3xl overflow-y-auto flex flex-col gap-0 p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle>New classification run</SheetTitle>
          <SheetDescription className="truncate">{documentTitle}</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          <ParseMethodSelector
            parserType={parserType}
            config={parserConfig}
            onParserTypeChange={setParserType}
            onConfigChange={setParserConfig}
            disabled={isSubmitting}
            compact
          />

          <Separator />

          <ClassificationConfig
            key={configKey}
            defaultValues={{
              labels: classifyConfig.labels,
              classifierType: classifyConfig.classifierType,
              classifierConfig: classifyConfig.classifierConfig,
            }}
            onChange={setClassifyConfig}
          />

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t flex justify-end shrink-0">
          <Button
            onClick={handleSubmit}
            disabled={
              classifyConfig.labels.length === 0 ||
              isSubmitting ||
              classifyConfig.classifierType === 'llamaindex_split'
            }
          >
            {isSubmitting ? 'Starting…' : 'Start classification'}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
