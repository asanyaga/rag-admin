import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useProject } from '@/contexts/ProjectContext'
import { useGoldenSetDetail } from '@/hooks/useGoldenSets'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { QueryList } from '@/components/evaluation/QueryList'
import { QueryEditor } from '@/components/evaluation/QueryEditor'

export default function GoldenSetEditorPage() {
  const { goldenSetId } = useParams<{ goldenSetId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const {
    goldenSet,
    selectedQueryId,
    selectedQuery,
    isLoading,
    setSelectedQueryId,
    addQuery,
    updateQuery,
    deleteQuery,
    addSource,
    deleteSource,
  } = useGoldenSetDetail(projectId, goldenSetId ?? null)

  const [addingQuery, setAddingQuery] = useState(false)
  const [newQueryText, setNewQueryText] = useState('')

  const handleAddQuery = async () => {
    if (!newQueryText.trim()) return
    await addQuery({ queryText: newQueryText.trim() })
    setNewQueryText('')
    setAddingQuery(false)
  }

  if (isLoading || !goldenSet) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/evaluation')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{goldenSet.name}</h1>
            <EvalStatusBadge status={goldenSet.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {goldenSet.queryCount} queries &middot;{' '}
            {goldenSet.documentCount} documents
          </p>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-[320px_1fr] gap-6 min-h-[500px]">
        {/* Left: Query list */}
        <QueryList
          queries={goldenSet.queries}
          selectedId={selectedQueryId}
          onSelect={setSelectedQueryId}
          onAdd={() => setAddingQuery(true)}
        />

        {/* Right: Query editor */}
        <div className="border rounded-lg p-4">
          {addingQuery ? (
            <div className="space-y-3">
              <h3 className="text-sm font-medium">New Query</h3>
              <Input
                value={newQueryText}
                onChange={(e) => setNewQueryText(e.target.value)}
                placeholder="Enter query text..."
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAddQuery()
                  }
                }}
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleAddQuery} disabled={!newQueryText.trim()}>
                  Add
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setAddingQuery(false)
                    setNewQueryText('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : selectedQuery ? (
            <QueryEditor
              query={selectedQuery}
              projectId={projectId!}
              onUpdateText={(qId, text) =>
                updateQuery(qId, { queryText: text })
              }
              onDelete={deleteQuery}
              onAddSource={addSource}
              onDeleteSource={deleteSource}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <p>Select a query or add a new one.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
