import { useClassificationRunBlocks } from '@/hooks/useClassificationRuns'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ClassificationLabelSection } from './ClassificationLabelSection'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  runId: string
  labelsRequested: string[]
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
}

export function ClassificationResultsViewer({ runId, labelsRequested, selectedBlockId, onBlockSelect }: Props) {
  const { blocks, isLoading, error } = useClassificationRunBlocks(runId)

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  const grouped = new Map<string | null, AnnotatedBlock[]>()
  for (const label of labelsRequested) {
    grouped.set(label, [])
  }
  grouped.set(null, [])
  for (const block of blocks) {
    const key = block.label ?? null
    if (!grouped.has(key)) {
      grouped.set(key, [])
    }
    grouped.get(key)!.push(block)
  }

  const unmatchedBlocks = grouped.get(null) ?? []

  return (
    <div className="space-y-2">
      {labelsRequested.map((label) => (
        <ClassificationLabelSection
          key={label}
          label={label}
          blocks={grouped.get(label) ?? []}
          selectedBlockId={selectedBlockId}
          onBlockSelect={onBlockSelect}
        />
      ))}
      {unmatchedBlocks.length > 0 && (
        <ClassificationLabelSection
          key="__unmatched__"
          label={null}
          blocks={unmatchedBlocks}
          selectedBlockId={selectedBlockId}
          onBlockSelect={onBlockSelect}
        />
      )}
    </div>
  )
}
