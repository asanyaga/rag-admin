import { useState } from 'react'
import type { ExtractionGroundTruthSet, ExtractionGroundTruthItem } from '@/types/extractionGroundTruth'
import type { DocumentListItem } from '@/types/document'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArrowLeft, Plus, Trash2, Pencil } from 'lucide-react'

interface GroundTruthSetDetailProps {
  set: ExtractionGroundTruthSet
  items: ExtractionGroundTruthItem[]
  documents: DocumentListItem[]
  isLoading: boolean
  onBack: () => void
  onAddItem: (documentId: string) => Promise<void>
  onDeleteItem: (itemId: string) => Promise<void>
  onEditItem: (item: ExtractionGroundTruthItem) => void
}

export function GroundTruthSetDetail({
  set,
  items,
  documents,
  isLoading,
  onBack,
  onAddItem,
  onDeleteItem,
  onEditItem,
}: GroundTruthSetDetailProps) {
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [selectedDocId, setSelectedDocId] = useState('')
  const [isAdding, setIsAdding] = useState(false)

  // Filter out documents already in the set
  const existingDocIds = new Set(items.map((i) => i.documentId))
  const availableDocs = documents.filter((d) => !existingDocIds.has(d.id) && d.status === 'ready')

  const handleAdd = async () => {
    if (!selectedDocId) return
    setIsAdding(true)
    try {
      await onAddItem(selectedDocId)
      setAddDialogOpen(false)
      setSelectedDocId('')
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold truncate">{set.name}</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <Badge variant="outline" className="text-xs">
              {set.extractionSchemaName}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {items.length} items
            </span>
          </div>
        </div>
        <Button size="sm" onClick={() => setAddDialogOpen(true)}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Add Document
        </Button>
      </div>

      {set.description && (
        <p className="text-sm text-muted-foreground">{set.description}</p>
      )}

      {/* Items list */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No documents labeled yet. Add a document to start labeling.
        </div>
      ) : (
        <div className="divide-y rounded-lg border">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 cursor-pointer"
              onClick={() => onEditItem(item)}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  {item.documentTitle || 'Untitled'}
                </p>
                <p className="text-xs text-muted-foreground">
                  {Object.keys(item.expectedData).length} fields labeled
                  {item.annotations?.quality ? (
                    <> · {String(item.annotations.quality)}</>
                  ) : null}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={(e) => {
                    e.stopPropagation()
                    onEditItem(item)
                  }}
                >
                  <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeleteItem(item.id)
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add document dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Document</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <Select value={selectedDocId} onValueChange={setSelectedDocId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a document" />
              </SelectTrigger>
              <SelectContent>
                {availableDocs.length === 0 ? (
                  <div className="py-2 px-3 text-sm text-muted-foreground">
                    No available documents
                  </div>
                ) : (
                  availableDocs.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.title}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAdd}
              disabled={!selectedDocId || isAdding}
            >
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
