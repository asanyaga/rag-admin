import { useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useParseAgentRuns } from '@/hooks/useParseAgentRuns'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'

export function ParseAgentRunsPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)

  const { runs, isLoading, isStarting, error, startRun } =
    useParseAgentRuns(projectId)

  const handleStart = async () => {
    if (!file) return
    try {
      const runId = await startRun(file)
      toast.success('Parse agent run started')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      navigate(`/parse-agent/runs/${runId}`)
    } catch (err) {
      toast.error('Failed to start run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  if (!projectId) {
    return (
      <Alert>
        <AlertDescription>Select a project to run the parse agent.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Parse Agent</h1>
        <p className="text-sm text-muted-foreground">
          Upload a document to start a traced parse run.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Input
          ref={fileRef}
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="max-w-sm"
        />
        <Button onClick={handleStart} disabled={!file || isStarting}>
          {isStarting ? 'Starting…' : 'Start run'}
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : runs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No runs yet.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {runs.map((run) => (
            <li key={run.id}>
              <Link
                to={`/parse-agent/runs/${run.id}`}
                className="flex items-center justify-between p-3 hover:bg-muted/50"
              >
                <span className="font-mono text-sm">{run.id.slice(0, 8)}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(run.startedAt).toLocaleString()}
                </span>
                <Badge variant="outline">{run.status}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
