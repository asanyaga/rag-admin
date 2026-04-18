import { Folder } from '@/types/folder'
import { FolderCreate } from '@/types/folder'
import { FolderEditPopover } from './FolderEditPopover'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Folder as FolderIcon, FolderOpen, Plus, Pencil, Files } from 'lucide-react'

interface FolderSidebarProps {
  folders: Folder[]
  selectedFolderId: string | null
  onSelectFolder: (folderId: string | null) => void
  onCreateFolder: (data: FolderCreate) => Promise<void>
  onUpdateFolder: (folderId: string, data: FolderCreate) => Promise<void>
  onDeleteFolder: (folderId: string) => Promise<void>
}

export function FolderSidebar({
  folders,
  selectedFolderId,
  onSelectFolder,
  onCreateFolder,
  onUpdateFolder,
  onDeleteFolder,
}: FolderSidebarProps) {
  return (
    <div className="flex flex-col w-52 shrink-0 border-r pr-2 space-y-0.5">
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Folders
        </span>
        <FolderEditPopover
          trigger={
            <Button variant="ghost" size="icon" className="h-6 w-6">
              <Plus className="h-3.5 w-3.5" />
            </Button>
          }
          onSave={onCreateFolder}
        />
      </div>

      {/* All documents */}
      <button
        onClick={() => onSelectFolder(null)}
        className={cn(
          'flex items-center gap-2 w-full rounded-md px-2 py-1.5 text-sm text-left hover:bg-muted transition-colors',
          selectedFolderId === null && 'bg-muted font-medium'
        )}
      >
        <Files className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="truncate">All documents</span>
      </button>

      {/* Folder list */}
      {folders.map((folder) => {
        const isSelected = selectedFolderId === folder.id
        const Icon = isSelected ? FolderOpen : FolderIcon
        return (
          <div key={folder.id} className="group flex items-center">
            <button
              onClick={() => onSelectFolder(folder.id)}
              className={cn(
                'flex items-center gap-2 flex-1 min-w-0 rounded-md px-2 py-1.5 text-sm text-left hover:bg-muted transition-colors',
                isSelected && 'bg-muted font-medium'
              )}
            >
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate flex-1">{folder.name}</span>
              {folder.documentCount > 0 && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  {folder.documentCount}
                </span>
              )}
            </button>

            <FolderEditPopover
              folder={folder}
              trigger={
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Pencil className="h-3 w-3" />
                </Button>
              }
              onSave={(data) => onUpdateFolder(folder.id, data)}
              onDelete={() => onDeleteFolder(folder.id)}
            />
          </div>
        )
      })}

      {folders.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted-foreground">No folders yet</p>
      )}
    </div>
  )
}
