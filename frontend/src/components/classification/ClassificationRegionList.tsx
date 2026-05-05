// frontend/src/components/classification/ClassificationRegionList.tsx
import { ClassificationRegionCard } from './ClassificationRegionCard'
import type { ClassificationRegion } from '@/types/classification'

interface Props {
  regions: ClassificationRegion[]
}

export function ClassificationRegionList({ regions }: Props) {
  if (regions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No regions identified.</p>
    )
  }
  return (
    <div className="space-y-3">
      {regions.map((region) => (
        <ClassificationRegionCard key={region.id} region={region} />
      ))}
    </div>
  )
}
