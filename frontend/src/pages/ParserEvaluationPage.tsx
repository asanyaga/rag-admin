import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { cn } from '@/lib/utils'
import { ParserEvalCasesTab } from '@/components/parser-eval/ParserEvalCasesTab'
import { ParserEvalRunsTab } from '@/components/parser-eval/ParserEvalRunsTab'

type Tab = 'cases' | 'runs'

export default function ParserEvaluationPage(): JSX.Element {
  const { currentProject } = useProject()
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>(
    searchParams.get('tab') === 'runs' ? 'runs' : 'cases'
  )

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage parser evaluation.
      </div>
    )
  }

  const tabBtn = (tab: Tab, label: string) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
        activeTab === tab && 'bg-background text-foreground shadow-sm'
      )}
    >
      {label}
    </button>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Parser Evaluation</h1>
        <p className="text-muted-foreground">
          Compare parsers against ground truth on quality, cost, and latency.
        </p>
      </div>

      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        {tabBtn('cases', 'Cases')}
        {tabBtn('runs', 'Runs')}
      </div>

      <div className={activeTab !== 'cases' ? 'hidden' : undefined}>
        <ParserEvalCasesTab projectId={currentProject.id} />
      </div>
      <div className={activeTab !== 'runs' ? 'hidden' : undefined}>
        <ParserEvalRunsTab projectId={currentProject.id} />
      </div>
    </div>
  )
}
