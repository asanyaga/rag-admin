import { useState } from 'react'
import type { ExtractionSchema } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ChevronDown, ChevronRight, Eye, Pencil, Plus, Trash2 } from 'lucide-react'

const TARGET_LABELS: Record<string, string> = {
  PER_DOC: 'Per Doc',
  PER_PAGE: 'Per Page',
  PER_TABLE_ROW: 'Per Row',
}

interface SchemaManagerProps {
  schemas: ExtractionSchema[]
  onEdit: (schema: ExtractionSchema) => void
  onDelete: (schemaId: string) => Promise<void>
  onCreate: () => void
}

export function SchemaManager({
  schemas,
  onEdit,
  onDelete,
  onCreate,
}: SchemaManagerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [previewSchema, setPreviewSchema] = useState<ExtractionSchema | null>(null)
  const [deletingSchema, setDeletingSchema] = useState<ExtractionSchema | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deletingSchema) return
    setIsDeleting(true)
    try {
      await onDelete(deletingSchema.id)
    } finally {
      setIsDeleting(false)
      setDeletingSchema(null)
    }
  }

  return (
    <>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="flex items-center justify-between">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1.5 px-2 -ml-2 text-sm font-medium">
              {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              Schemas
              <span className="text-muted-foreground font-normal">({schemas.length})</span>
            </Button>
          </CollapsibleTrigger>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onCreate}>
            <Plus className="h-3 w-3 mr-1" />
            New
          </Button>
        </div>

        <CollapsibleContent className="mt-1">
          {schemas.length === 0 ? (
            <div className="rounded-md border border-dashed p-4 text-center">
              <p className="text-sm text-muted-foreground">No schemas yet.</p>
              <Button variant="link" size="sm" className="mt-1 text-xs" onClick={onCreate}>
                Create your first schema
              </Button>
            </div>
          ) : (
            <div className="space-y-1">
              {schemas.map((schema) => (
                <div
                  key={schema.id}
                  className="group flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{schema.name}</span>
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0 shrink-0">
                        {TARGET_LABELS[schema.extractionTarget] ?? schema.extractionTarget}
                      </Badge>
                    </div>
                    {schema.description && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {schema.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title="Preview schema"
                      onClick={() => setPreviewSchema(previewSchema?.id === schema.id ? null : schema)}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title="Edit schema"
                      onClick={() => onEdit(schema)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      title="Delete schema"
                      onClick={() => setDeletingSchema(schema)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* JSON preview */}
          {previewSchema && (
            <div className="mt-2 rounded-md border bg-muted/50 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium">{previewSchema.name} - Schema Definition</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => setPreviewSchema(null)}
                >
                  Close
                </Button>
              </div>
              <pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(previewSchema.schemaDefinition, null, 2)}
              </pre>
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>

      {/* Delete confirmation */}
      <AlertDialog open={!!deletingSchema} onOpenChange={(open) => !open && setDeletingSchema(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete schema</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{deletingSchema?.name}</strong>?
              This may affect existing extraction results that reference this schema.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
