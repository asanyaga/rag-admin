import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { EvalRunsTab } from '@/components/evaluation/EvalRunsTab'
import { GoldenSetsTab } from '@/components/evaluation/GoldenSetsTab'

export default function EvaluationPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const {
    runs,
    isLoading: runsLoading,
    deleteRun,
  } = useEvalRuns(projectId)

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
      <div>
        <h1 className="text-2xl font-bold">Evaluation</h1>
        <p className="text-muted-foreground">
          Measure and compare retrieval quality using golden sets.
        </p>
      </div>

      <Tabs defaultValue="runs">
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="golden-sets">Golden Sets</TabsTrigger>
        </TabsList>
        <TabsContent value="runs" className="mt-4">
          <EvalRunsTab
            runs={runs}
            isLoading={runsLoading}
            onDelete={deleteRun}
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
