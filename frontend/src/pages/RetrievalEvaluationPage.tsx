import { useProject } from '@/contexts/ProjectContext'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { useExperiments } from '@/hooks/useExperiments'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EvalRunsTab } from '@/components/evaluation/EvalRunsTab'
import { GoldenSetsTab } from '@/components/evaluation/GoldenSetsTab'
import { ExperimentsTab } from '@/components/evaluation/ExperimentsTab'

export default function RetrievalEvaluationPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { runs, isLoading: runsLoading, deleteRun } = useEvalRuns(projectId)
  const { experiments, isLoading: experimentsLoading, createExperiment, deleteExperiment } =
    useExperiments(projectId)
  const { goldenSets, isLoading: gsLoading, createGoldenSet, deleteGoldenSet } =
    useGoldenSets(projectId)

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage evaluations.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Retrieval Evaluation</h1>
        <p className="text-muted-foreground">
          Measure and compare retrieval quality using golden sets.
        </p>
      </div>
      <Tabs defaultValue="runs">
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="experiments">Experiments</TabsTrigger>
          <TabsTrigger value="golden-sets">Golden Sets</TabsTrigger>
        </TabsList>
        <TabsContent value="runs" className="mt-4">
          <EvalRunsTab runs={runs} isLoading={runsLoading} onDelete={deleteRun} />
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
  )
}
