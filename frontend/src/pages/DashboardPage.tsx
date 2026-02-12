import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useIndexes } from '@/hooks/useIndexes'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  FileText,
  Database,
  FlaskConical,
  ClipboardList,
  CheckCircle,
  Loader2,
  XCircle,
  ArrowRight,
} from 'lucide-react'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { documents, isLoading: docsLoading, fetchDocuments } = useDocuments(projectId)
  const { indexes, isLoading: idxLoading, fetchIndexes } = useIndexes(projectId)
  const { runs, isLoading: runsLoading, fetchRuns } = useEvalRuns(projectId)
  const { goldenSets, isLoading: gsLoading, fetchGoldenSets } = useGoldenSets(projectId)

  useEffect(() => {
    if (projectId) {
      fetchDocuments()
      fetchIndexes()
      fetchRuns()
      fetchGoldenSets()
    }
  }, [projectId, fetchDocuments, fetchIndexes, fetchRuns, fetchGoldenSets])

  const isLoading = docsLoading || idxLoading || runsLoading || gsLoading

  // Status breakdowns
  const docsByStatus = {
    ready: documents.filter((d) => d.status === 'ready').length,
    processing: documents.filter((d) => d.status === 'processing').length,
    failed: documents.filter((d) => d.status === 'failed').length,
  }

  const idxByStatus = {
    ready: indexes.filter((i) => i.status === 'ready').length,
    processing: indexes.filter((i) => i.status === 'processing').length,
    failed: indexes.filter((i) => i.status === 'failed').length,
    created: indexes.filter((i) => i.status === 'created').length,
  }

  const runsByStatus = {
    completed: runs.filter((r) => r.status === 'completed').length,
    running: runs.filter((r) => r.status === 'running').length,
    failed: runs.filter((r) => r.status === 'failed').length,
    pending: runs.filter((r) => r.status === 'pending').length,
  }

  const totalChunks = indexes.reduce((sum, i) => sum + i.chunkCount, 0)

  const statCards = [
    {
      title: 'Documents',
      value: documents.length,
      icon: FileText,
      color: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-100 dark:bg-blue-950/40',
      borderColor: 'border-l-blue-500',
      href: '/documents',
      breakdown: [
        { label: 'Ready', count: docsByStatus.ready, color: 'bg-green-500' },
        { label: 'Processing', count: docsByStatus.processing, color: 'bg-blue-500' },
        { label: 'Failed', count: docsByStatus.failed, color: 'bg-red-500' },
      ],
    },
    {
      title: 'Indexes',
      value: indexes.length,
      icon: Database,
      color: 'text-teal-600 dark:text-teal-400',
      bgColor: 'bg-teal-100 dark:bg-teal-950/40',
      borderColor: 'border-l-teal-500',
      href: '/index',
      subtitle: `${totalChunks.toLocaleString()} chunks`,
      breakdown: [
        { label: 'Ready', count: idxByStatus.ready, color: 'bg-green-500' },
        { label: 'Processing', count: idxByStatus.processing, color: 'bg-blue-500' },
        { label: 'Draft', count: idxByStatus.created, color: 'bg-muted-foreground' },
        { label: 'Failed', count: idxByStatus.failed, color: 'bg-red-500' },
      ],
    },
    {
      title: 'Eval Runs',
      value: runs.length,
      icon: FlaskConical,
      color: 'text-amber-600 dark:text-amber-400',
      bgColor: 'bg-amber-100 dark:bg-amber-950/40',
      borderColor: 'border-l-amber-500',
      href: '/evaluation',
      breakdown: [
        { label: 'Completed', count: runsByStatus.completed, color: 'bg-green-500' },
        { label: 'Running', count: runsByStatus.running, color: 'bg-blue-500' },
        { label: 'Pending', count: runsByStatus.pending, color: 'bg-amber-500' },
        { label: 'Failed', count: runsByStatus.failed, color: 'bg-red-500' },
      ],
    },
    {
      title: 'Golden Sets',
      value: goldenSets.length,
      icon: ClipboardList,
      color: 'text-violet-600 dark:text-violet-400',
      bgColor: 'bg-violet-100 dark:bg-violet-950/40',
      borderColor: 'border-l-violet-500',
      href: '/evaluation',
    },
  ]

  // Recent activity: combine indexes and eval runs, sort by date
  const recentItems = [
    ...indexes.slice(0, 5).map((i) => ({
      id: i.id,
      type: 'index' as const,
      name: i.name,
      status: i.status,
      date: i.createdAt,
      href: `/index/${i.id}`,
    })),
    ...runs.slice(0, 5).map((r) => ({
      id: r.id,
      type: 'eval' as const,
      name: r.name,
      status: r.status,
      date: r.createdAt,
      href: `/evaluation/runs/${r.id}`,
    })),
  ]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 6)

  const statusIcon = (status: string) => {
    switch (status) {
      case 'ready':
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
      case 'processing':
      case 'running':
      case 'pending':
        return <Loader2 className="h-4 w-4 text-blue-600 dark:text-blue-400 animate-spin" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
      default:
        return <div className="h-4 w-4 rounded-full border-2" />
    }
  }

  return (
    <div className="-m-6">
      {/* Header */}
      <div className="px-6 py-5 border-b bg-background">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        {currentProject && (
          <p className="text-sm text-muted-foreground mt-0.5">
            {currentProject.name}
          </p>
        )}
      </div>

      <div className="p-6 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((card) => (
            <Card
              key={card.title}
              className={`border-l-4 ${card.borderColor} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => navigate(card.href)}
            >
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {card.title}
                </CardTitle>
                <div className={`p-2 rounded-lg ${card.bgColor}`}>
                  <card.icon className={`h-4 w-4 ${card.color}`} />
                </div>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-8 w-16" />
                ) : (
                  <>
                    <div className="text-2xl font-bold">{card.value}</div>
                    {card.subtitle && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {card.subtitle}
                      </p>
                    )}
                    {card.breakdown && card.value > 0 && (
                      <div className="mt-3 space-y-1.5">
                        {/* Mini bar */}
                        <div className="flex h-1.5 rounded-full overflow-hidden bg-muted">
                          {card.breakdown
                            .filter((b) => b.count > 0)
                            .map((b) => (
                              <div
                                key={b.label}
                                className={`${b.color} transition-all`}
                                style={{
                                  width: `${(b.count / card.value) * 100}%`,
                                }}
                              />
                            ))}
                        </div>
                        {/* Legend */}
                        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                          {card.breakdown
                            .filter((b) => b.count > 0)
                            .map((b) => (
                              <span
                                key={b.label}
                                className="flex items-center gap-1 text-[10px] text-muted-foreground"
                              >
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${b.color}`}
                                />
                                {b.count} {b.label}
                              </span>
                            ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : recentItems.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No activity yet. Create an index or run an evaluation to get started.
              </p>
            ) : (
              <div className="divide-y divide-border">
                {recentItems.map((item) => (
                  <div
                    key={`${item.type}-${item.id}`}
                    onClick={() => navigate(item.href)}
                    className="flex items-center gap-3 py-3 cursor-pointer hover:bg-primary/5 -mx-6 px-6 transition-colors"
                  >
                    {statusIcon(item.status)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.type === 'index' ? 'Index' : 'Eval Run'} &middot;{' '}
                        {new Date(item.date).toLocaleDateString()}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground/40 shrink-0" />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
