import { useState } from 'react'
import type { ExtractionGroundTruthSet } from '@/types/extractionGroundTruth'
import type { ExtractionSchema } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Trash2 } from 'lucide-react'

interface GroundTruthSetListProps {
  sets: ExtractionGroundTruthSet[]
  schemas: ExtractionSchema[]
  isLoading: boolean
  onSelect: (set: ExtractionGroundTruthSet) => void
  onCreate: (data: { extractionSchemaId: string; name: string; description?: string }) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

export function GroundTruthSetList({
  sets,
  schemas,
  isLoading,
  onSelect,
  onCreate,
  onDelete,
}: GroundTruthSetListProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [schemaId, setSchemaId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleCreate = async () => {
    if (!name.trim() || !schemaId) return
    setIsSubmitting(true)
    try {
      await onCreate({ extractionSchemaId: schemaId, name: name.trim(), description: description.trim() || undefined })
      setDialogOpen(false)
      setName('')
      setDescription('')
      setSchemaId('')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Ground Truth Sets</h2>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Set
        </Button>
      </div>

      {sets.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No ground truth sets yet. Create one to start labeling.
        </div>
      ) : (
        <div className="space-y-2">
          {sets.map((set) => (
            <Card
              key={set.id}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => onSelect(set)}
            >
              <CardContent className="py-3 px-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{set.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className="text-xs">
                        {set.extractionSchemaName}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {set.itemCount} items
                      </span>
                    </div>
                    {set.description && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                        {set.description}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(set.id)
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Ground Truth Set</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Extraction Schema</Label>
              <Select value={schemaId} onValueChange={setSchemaId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a schema" />
                </SelectTrigger>
                <SelectContent>
                  {schemas.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Kenyan Receipts v1"
              />
            </div>
            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this ground truth set..."
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || !schemaId || isSubmitting}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
