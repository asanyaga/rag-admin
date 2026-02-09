import { useState } from 'react'
import { Trash2, Plus, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { SourcesList } from './SourcesList'
import { AddSourceDialog } from './AddSourceDialog'
import type { GoldenSetQuery, SourceCreate } from '@/types/golden-set'

interface QueryEditorProps {
  query: GoldenSetQuery
  projectId: string
  onUpdateText: (queryId: string, text: string) => Promise<void>
  onDelete: (queryId: string) => Promise<void>
  onAddSource: (queryId: string, data: SourceCreate) => Promise<void>
  onDeleteSource: (queryId: string, sourceId: string) => Promise<void>
}

export function QueryEditor({
  query,
  projectId,
  onUpdateText,
  onDelete,
  onAddSource,
  onDeleteSource,
}: QueryEditorProps) {
  const [editingText, setEditingText] = useState<string | null>(null)
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
    </div>
  )
}
