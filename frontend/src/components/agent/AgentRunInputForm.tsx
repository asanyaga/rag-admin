import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Play } from 'lucide-react'
import type { StartAgentRunRequest } from '@/types/agent'

interface AgentRunInputFormProps {
  agentDefinitionId: string
  isStarting: boolean
  onStart: (request: StartAgentRunRequest) => Promise<void>
}

export function AgentRunInputForm({
  agentDefinitionId,
  isStarting,
  onStart,
}: AgentRunInputFormProps) {
  const [initialStateJson, setInitialStateJson] = useState('{}')
  const [jsonError, setJsonError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setJsonError(null)
    let initialState: Record<string, unknown>
    try {
      initialState = JSON.parse(initialStateJson)
    } catch {
      setJsonError('Invalid JSON — please fix before starting.')
      return
    }
    await onStart({ agentDefinitionId, initialState })
    setInitialStateJson('{}')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Initial State (JSON)</Label>
        <Textarea
          className="font-mono text-xs"
          rows={5}
          value={initialStateJson}
          onChange={(e) => setInitialStateJson(e.target.value)}
          placeholder="{}"
        />
        {jsonError && (
          <p className="text-xs text-destructive">{jsonError}</p>
        )}
      </div>
      <Button
        type="submit"
        size="sm"
        disabled={isStarting}
      >
        <Play className="h-4 w-4 mr-1.5" />
        {isStarting ? 'Starting...' : 'Run'}
      </Button>
    </form>
  )
}
