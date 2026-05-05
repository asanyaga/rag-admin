// frontend/src/components/classification/ClassificationRegionCard.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { ClassificationRegion } from '@/types/classification'

interface Props {
  region: ClassificationRegion
}

export function ClassificationRegionCard({ region }: Props) {
  const [reasoningOpen, setReasoningOpen] = useState(false)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">{region.label}</CardTitle>
          <div className="flex items-center gap-2">
            {region.confidence !== null && (
              <Badge variant="outline">
                {(region.confidence * 100).toFixed(0)}% confidence
              </Badge>
            )}
            <span className="text-sm text-muted-foreground">
              Pages {region.pageStart + 1}–{region.pageEnd + 1}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-2">
        <p>{region.blockIds.length} blocks</p>
        {region.reasoning && (
          <div>
            <button
              className="flex items-center gap-1 text-xs font-medium hover:text-foreground"
              onClick={() => setReasoningOpen((v) => !v)}
            >
              {reasoningOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Reasoning
            </button>
            {reasoningOpen && (
              <p className="mt-1 text-xs leading-relaxed">{region.reasoning}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
