import { useState } from 'react'
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

interface CreateGoldenSetDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: GoldenSetCreate) => Promise<void>
}

export function CreateGoldenSetDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateGoldenSetDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setIsSubmitting(true)
    try {
      await onCreate({ name: name.trim(), description: description.trim() || undefined })
      setName('')
      setDescription('')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
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
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
