import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { cn } from '@/lib/utils'
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { useExperiments } from '@/hooks/useExperiments'
import { EvalRunsTab } from '@/components/evaluation/EvalRunsTab'
import { GoldenSetsTab } from '@/components/evaluation/GoldenSetsTab'
import { ExperimentsTab } from '@/components/evaluation/ExperimentsTab'
import { ExtractionEvalRunsTab } from '@/components/extraction-eval/ExtractionEvalRunsTab'
import { ExtractionGroundTruthTab } from '@/components/extraction-ground-truth/ExtractionGroundTruthTab'
import { Search, FileSearch } from 'lucide-react'

type Domain = 'retrieval' | 'extraction'
type ExtractionTab = 'runs' | 'ground-truth'

export default function EvaluationPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const [domain, setDomain] = useState<Domain>('retrieval')
  const [extractionTab, setExtractionTab] = useState<ExtractionTab>('runs')

  const {
    runs,
    isLoading: runsLoading,
    deleteRun,
  } = useEvalRuns(projectId)

  const {
    experiments,
    isLoading: experimentsLoading,
    createExperiment,
    deleteExperiment,
  } = useExperiments(projectId)

  const {
    goldenSets,
    isLoading: gsLoading,
    createGoldenSet,
    deleteGoldenSet,
  } = useGoldenSets(projectId)

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage evaluations.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Evaluation</h1>
          <p className="text-muted-foreground">
            {domain === 'retrieval'
              ? 'Measure and compare retrieval quality using golden sets.'
              : 'Measure extraction quality against ground truth.'}
          </p>
        </div>
        <ToggleGroup
          type="single"
          value={domain}
          onValueChange={(v) => { if (v) setDomain(v as Domain) }}
          className="border rounded-lg"
        >
          <ToggleGroupItem value="retrieval" aria-label="Retrieval evaluation" className="gap-1.5 text-xs px-3">
            <Search className="h-3.5 w-3.5" />
            Retrieval
          </ToggleGroupItem>
          <ToggleGroupItem value="extraction" aria-label="Extraction evaluation" className="gap-1.5 text-xs px-3">
            <FileSearch className="h-3.5 w-3.5" />
            Extraction
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {/* Retrieval domain — uses shadcn Tabs */}
      <div className={domain !== 'retrieval' ? 'hidden' : undefined}>
        <Tabs defaultValue="runs">
          <TabsList>
            <TabsTrigger value="runs">Runs</TabsTrigger>
            <TabsTrigger value="experiments">Experiments</TabsTrigger>
            <TabsTrigger value="golden-sets">Golden Sets</TabsTrigger>
          </TabsList>
          <TabsContent value="runs" className="mt-4">
            <EvalRunsTab
              runs={runs}
              isLoading={runsLoading}
              onDelete={deleteRun}
            />
          </TabsContent>
          <TabsContent value="experiments" className="mt-4">
            <ExperimentsTab
              experiments={experiments}
              isLoading={experimentsLoading}
              onCreate={createExperiment}
              onDelete={deleteExperiment}
            />
          </TabsContent>
          <TabsContent value="golden-sets" className="mt-4">
            <GoldenSetsTab
              goldenSets={goldenSets}
              isLoading={gsLoading}
              onCreate={createGoldenSet}
              onDelete={deleteGoldenSet}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* Extraction domain — no Radix Tabs, plain state-based visibility */}
      <div className={domain !== 'extraction' ? 'hidden' : undefined}>
        {/* Tab bar */}
        <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground mb-4">
          <button
            onClick={() => setExtractionTab('runs')}
            className={cn(
              'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
              extractionTab === 'runs' && 'bg-background text-foreground shadow-sm'
            )}
          >
            Runs
          </button>
          <button
            onClick={() => setExtractionTab('ground-truth')}
            className={cn(
              'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
              extractionTab === 'ground-truth' && 'bg-background text-foreground shadow-sm'
            )}
          >
            Ground Truth
          </button>
        </div>

        {/* Runs content */}
        <div className={extractionTab !== 'runs' ? 'hidden' : undefined}>
          <ExtractionEvalRunsTab projectId={currentProject.id} />
        </div>

        {/* Ground truth content — always mounted, hidden via CSS */}
        <div className={extractionTab !== 'ground-truth' ? 'hidden' : undefined}>
          <ExtractionGroundTruthTab projectId={currentProject.id} />
        </div>
      </div>
    </div>
  )
}
