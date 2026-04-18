import { useState } from 'react'
import { Folder } from '@/types/folder'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { X } from 'lucide-react'

interface BulkActionBarProps {
  selectedCount: number
  folders: Folder[]
  onMove: (folderId: string | null) => Promise<void>
  onClearSelection: () => void
}

const UNFILE_VALUE = '__unfile__'

export function BulkActionBar({
  selectedCount,
  folders,
  onMove,
  onClearSelection,
}: BulkActionBarProps) {
  const [isMoving, setIsMoving] = useState(false)

  const handleMove = async (value: string) => {
    setIsMoving(true)
    try {
      await onMove(value === UNFILE_VALUE ? null : value)
      onClearSelection()
    } finally {
      setIsMoving(false)
    }
  }

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-muted rounded-md border">
      <span className="text-sm font-medium">
        {selectedCount} selected
      </span>

      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Move to:</span>
        <Select onValueChange={handleMove} disabled={isMoving}>
          <SelectTrigger className="h-8 w-44 text-sm">
            <SelectValue placeholder="Choose folder…" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={UNFILE_VALUE}>
              <span className="text-muted-foreground">No folder (unfile)</span>
            </SelectItem>
            {folders.map((folder) => (
              <SelectItem key={folder.id} value={folder.id}>
                {folder.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 ml-auto"
        onClick={onClearSelection}
        disabled={isMoving}
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  )
}
