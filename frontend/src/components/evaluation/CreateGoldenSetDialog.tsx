import { useState } from 'react'
import { Pencil, Sparkles } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { GoldenSetCreate } from '@/types/golden-set'

type CreationMethod = 'manual' | 'auto-generate'

interface CreateGoldenSetDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: GoldenSetCreate, method: CreationMethod) => Promise<void>
}

export function CreateGoldenSetDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateGoldenSetDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState<CreationMethod | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !method) return
    setIsSubmitting(true)
    try {
      await onCreate(
        { name: name.trim(), description: description.trim() || undefined },
        method
      )
      setName('')
      setDescription('')
      setMethod(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleOpenChange = (o: boolean) => {
    if (!o) {
      setName('')
      setDescription('')
      setMethod(null)
    }
    onOpenChange(o)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Golden Set</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="gs-name">Name</Label>
            <Input
              id="gs-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Product FAQ Queries"
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="gs-description">Description</Label>
            <Textarea
              id="gs-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description..."
              rows={2}
            />
          </div>

          {/* Method picker */}
          <div className="space-y-2">
            <Label>Creation Method</Label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setMethod('manual')}
                className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 text-center transition-colors ${
                  method === 'manual'
                    ? 'border-primary bg-primary/5'
                    : 'border-muted hover:border-muted-foreground/30'
                }`}
              >
                <Pencil className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm font-medium">Manual</span>
                <span className="text-xs text-muted-foreground">
                  Add queries by hand
                </span>
              </button>
              <button
                type="button"
                onClick={() => setMethod('auto-generate')}
                className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 text-center transition-colors ${
                  method === 'auto-generate'
                    ? 'border-primary bg-primary/5'
                    : 'border-muted hover:border-muted-foreground/30'
                }`}
              >
                <Sparkles className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm font-medium">Auto-Generate</span>
                <span className="text-xs text-muted-foreground">
                  AI generates from docs
                </span>
              </button>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || !method || isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
