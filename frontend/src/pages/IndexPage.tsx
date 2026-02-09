/**
 * Index management page
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useIndexes } from '@/hooks/useIndexes'
import { useDocuments } from '@/hooks/useDocuments'
import { IndexListItem } from '@/types/index'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { IndexCard } from '@/components/indexes/IndexCard'
import { Plus, Database, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

export default function IndexPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const {
    indexes,
    isLoading,
    error,
    deleteIndex,
    processIndex,
    retryIndex,
  } = useIndexes(currentProject?.id ?? null)
  const { documents } = useDocuments(currentProject?.id ?? null)

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState<IndexListItem | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleView = (index: IndexListItem) => {
    navigate(`/index/${index.id}`)
  }

  const handleEdit = () => {
    // For now, edit opens the create dialog pre-filled
    // This would need a separate edit dialog in a real implementation
    toast.info('Edit functionality coming soon')
  }

  const handleDeleteClick = (index: IndexListItem) => {
    setSelectedIndex(index)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedIndex) return

    setIsDeleting(true)
    try {
      await deleteIndex(selectedIndex.id)
      setDeleteDialogOpen(false)
      setSelectedIndex(null)
      toast.success('Index deleted successfully')
    } catch {
      // Error handled by hook
    } finally {
      setIsDeleting(false)
    }
  }

  const handleProcess = async (index: IndexListItem) => {
    try {
      await processIndex(index.id)
      toast.success('Processing started')
    } catch (error) {
      if (error instanceof Error) {
        toast.error(error.message)
      }
    }
  }

  const handleRetry = async (index: IndexListItem) => {
    try {
      await retryIndex(index.id)
      toast.success('Retry started')
    } catch (error) {
      if (error instanceof Error) {
        toast.error(error.message)
      }
    }
  }

  // Filter to only ready documents
  const readyDocuments = documents.filter((d) => d.status === 'ready')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Indexes</h1>
          <p className="text-muted-foreground mt-1">
            Create and manage vector indexes for RAG
          </p>
        </div>
        <Button
          onClick={() => navigate('/index/create')}
          disabled={!currentProject || readyDocuments.length === 0}
        >
          <Plus className="h-4 w-4 mr-2" />
          New Index
        </Button>
      </div>

      {/* No project selected warning */}
      {!currentProject && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Please select a project to manage indexes.
          </AlertDescription>
        </Alert>
      )}

      {/* No documents warning */}
      {currentProject && readyDocuments.length === 0 && !isLoading && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Upload and process some documents first before creating an index.{' '}
            <Button
              variant="link"
              className="p-0 h-auto"
              onClick={() => navigate('/documents')}
            >
              Go to Documents
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      ) : indexes.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Database className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No indexes yet</h3>
          <p className="text-muted-foreground mb-4 max-w-sm">
            Create your first index to start chunking and embedding your
            documents for RAG retrieval.
          </p>
          {readyDocuments.length > 0 && (
            <Button onClick={() => navigate('/index/create')}>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Index
            </Button>
          )}
        </div>
      ) : (
        /* Index grid */
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {indexes.map((idx) => (
            <IndexCard
              key={idx.id}
              index={idx}
              onView={handleView}
              onEdit={handleEdit}
              onDelete={handleDeleteClick}
              onProcess={handleProcess}
              onRetry={handleRetry}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Index</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete "{selectedIndex?.name}
              "? This will also delete all {selectedIndex?.chunkCount} chunks.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
