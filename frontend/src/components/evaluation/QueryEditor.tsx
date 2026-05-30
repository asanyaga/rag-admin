import { useState } from 'react'
import { Trash2, Plus, Check, X } from 'lucide-react'
import { format } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { SourcesList } from './SourcesList'
import { AddSourceDialog } from './AddSourceDialog'
import type { GoldenSetQuery, SourceCreate } from '@/types/golden-set'

interface QueryEditorProps {
  query: GoldenSetQuery
  projectId: string
  onUpdateText: (queryId: string, text: string) => Promise<void>
  onUpdateReferenceAnswer: (queryId: string, answer: string | null) => Promise<void>
  onDelete: (queryId: string) => Promise<void>
  onAddSource: (queryId: string, data: SourceCreate) => Promise<void>
  onDeleteSource: (queryId: string, sourceId: string) => Promise<void>
}

export function QueryEditor({
  query,
  projectId,
  onUpdateText,
  onUpdateReferenceAnswer,
  onDelete,
  onAddSource,
  onDeleteSource,
}: QueryEditorProps) {
  const [editingText, setEditingText] = useState<string | null>(null)
  const [editingAnswer, setEditingAnswer] = useState<string | null>(null)
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false)

  const handleSaveText = async () => {
    if (editingText !== null && editingText.trim() !== query.queryText) {
      await onUpdateText(query.id, editingText.trim())
    }
    setEditingText(null)
  }

  const handleCancelEdit = () => {
    setEditingText(null)
  }

  const handleSaveAnswer = async () => {
    if (editingAnswer !== null) {
      const trimmed = editingAnswer.trim()
      const newVal = trimmed || null
      if (newVal !== (query.referenceAnswer ?? null)) {
        await onUpdateReferenceAnswer(query.id, newVal)
      }
    }
    setEditingAnswer(null)
  }

  const handleCancelAnswer = () => {
    setEditingAnswer(null)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          {editingText !== null ? (
            <div className="space-y-2">
              <Textarea
                value={editingText}
                onChange={(e) => setEditingText(e.target.value)}
                rows={3}
                autoFocus
              />
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={handleSaveText}>
                  <Check className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" onClick={handleCancelEdit}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : (
            <p
              className="text-sm cursor-pointer hover:bg-accent rounded p-2 -m-2"
              onClick={() => setEditingText(query.queryText)}
            >
              {query.queryText}
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 text-muted-foreground hover:text-destructive"
          onClick={() => onDelete(query.id)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <Separator />

      {/* Reference Answer */}
      <div>
        <Label className="text-sm font-medium">Reference Answer</Label>
        <p className="text-xs text-muted-foreground mb-1.5">
          Optional ideal answer used for answer evaluation judging.
        </p>
        {editingAnswer !== null ? (
          <div className="space-y-2">
            <Textarea
              value={editingAnswer}
              onChange={(e) => setEditingAnswer(e.target.value)}
              rows={3}
              placeholder="Enter the expected ideal answer..."
              autoFocus
            />
            <div className="flex gap-1">
              <Button size="sm" variant="ghost" onClick={handleSaveAnswer}>
                <Check className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={handleCancelAnswer}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ) : (
          <p
            className="text-sm cursor-pointer hover:bg-accent rounded p-2 -m-2 min-h-[2rem]"
            onClick={() => setEditingAnswer(query.referenceAnswer ?? '')}
          >
            {query.referenceAnswer || (
              <span className="text-muted-foreground italic">Click to add reference answer...</span>
            )}
          </p>
        )}
      </div>

      <Separator />

      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium">Expected Sources</h4>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSourceDialogOpen(true)}
          >
            <Plus className="mr-1 h-3.5 w-3.5" />
            Add Source
          </Button>
        </div>
        <SourcesList
          sources={query.sources}
          onDelete={(sourceId) => onDeleteSource(query.id, sourceId)}
        />
      </div>

      <AddSourceDialog
        open={sourceDialogOpen}
        onOpenChange={setSourceDialogOpen}
        projectId={projectId}
        onAdd={(data) => onAddSource(query.id, data)}
      />

      {/* Metadata footer */}
      <Separator />
      <div className="space-y-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-4">
          <span>
            <span className="font-medium">Origin:</span>{' '}
            {query.sourceMethod === 'auto_generated'
              ? 'Auto-generated'
              : query.sourceMethod === 'imported'
              ? 'Imported'
              : 'Manual'}
          </span>
          <span>
            <span className="font-medium">Created:</span>{' '}
            {format(new Date(query.createdAt), 'MMM d, yyyy')}
          </span>
          {query.questionType && (
            <span>
              <span className="font-medium">Type:</span> {query.questionType}
            </span>
          )}
        </div>
        {query.reasoning && (
          <div className="rounded bg-muted/50 p-2 leading-relaxed">
            {query.reasoning}
          </div>
        )}
      </div>
    </div>
  )
}
