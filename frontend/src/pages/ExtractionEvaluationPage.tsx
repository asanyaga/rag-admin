import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { cn } from '@/lib/utils'
import { ExtractionEvalRunsTab } from '@/components/extraction-eval/ExtractionEvalRunsTab'
import { ExtractionGroundTruthTab } from '@/components/extraction-ground-truth/ExtractionGroundTruthTab'

type Tab = 'runs' | 'ground-truth'

export default function ExtractionEvaluationPage(): JSX.Element {
  const { currentProject } = useProject()
  const [activeTab, setActiveTab] = useState<Tab>('runs')

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage extraction evaluation.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Extraction Evaluation</h1>
        <p className="text-muted-foreground">
          Measure extraction quality against ground truth.
        </p>
      </div>

      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        <button
          onClick={() => setActiveTab('runs')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'runs' && 'bg-background text-foreground shadow-sm'
          )}
        >
          Runs
        </button>
        <button
          onClick={() => setActiveTab('ground-truth')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'ground-truth' && 'bg-background text-foreground shadow-sm'
          )}
        >
          Ground Truth
        </button>
      </div>

      <div className={activeTab !== 'runs' ? 'hidden' : undefined}>
        <ExtractionEvalRunsTab projectId={currentProject.id} />
      </div>

      <div className={activeTab !== 'ground-truth' ? 'hidden' : undefined}>
        <ExtractionGroundTruthTab projectId={currentProject.id} />
      </div>
    </div>
  )
}
