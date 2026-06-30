import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ClassificationConfig } from './ClassificationConfig'
import type { ClassificationConfigValue } from './ClassificationConfig'

// Re-export so existing imports of ClassificationRunFormValues continue to work
export type { ClassificationConfigValue as ClassificationRunFormValues }

interface Props {
  defaultValues?: Partial<ClassificationConfigValue>
  onSubmit: (values: ClassificationConfigValue) => void
  isSubmitting?: boolean
  submitLabel?: string
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [config, setConfig] = useState<ClassificationConfigValue>({
    labels: defaultValues?.labels ?? [],
    classifierType: defaultValues?.classifierType ?? 'llm',
  })

  return (
    <div className="space-y-6">
      <ClassificationConfig defaultValues={defaultValues} onChange={setConfig} />
      <Button
        onClick={() => onSubmit(config)}
        disabled={
          config.labels.length === 0 ||
          isSubmitting ||
          config.classifierType === 'llamaindex_split'
        }
      >
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
