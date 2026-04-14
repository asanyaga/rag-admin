import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Plus, Database } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import { useDataStores } from '@/hooks/useDataStores'
import { useProject } from '@/contexts/ProjectContext'
import { DataStoreCreateDialog } from '@/components/data-stores/DataStoreCreateDialog'
import * as extractionApi from '@/api/extraction'
import type { DataStore } from '@/types/dataStore'
import type { ExtractionSchema } from '@/types/extraction'

export default function DataStoresPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null
  const navigate = useNavigate()

  const { dataStores, isLoading, error, createDataStore, deleteDataStore } = useDataStores(projectId)
  const [extractionSchemas, setExtractionSchemas] = useState<ExtractionSchema[]>([])

  const [createOpen, setCreateOpen] = useState(false)

  // Fetch extraction schemas when create dialog opens (for seed feature)
  useEffect(() => {
    if (createOpen && projectId) {
      extractionApi.listExtractionSchemas(projectId).then(setExtractionSchemas).catch(() => {})
    }
  }, [createOpen, projectId])

  const handleCreate = async (data: Parameters<typeof createDataStore>[0]) => {
    const store = await createDataStore(data)
    toast.success(`Data store "${store.name}" created`)
  }

  const handleDelete = async (store: DataStore) => {
    try {
      await deleteDataStore(store.id)
      toast.success(`Data store "${store.name}" deleted`)
    } catch {
      toast.error('Failed to delete data store')
    }
  }

  if (!projectId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Select a project to manage data stores.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Data Stores</h1>
          <p className="text-muted-foreground">Manage project data tables</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Data Store
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : dataStores.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center border rounded-lg">
          <Database className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="font-medium mb-1">No data stores yet</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Create a data store to manage project data.
          </p>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Data Store
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-3 px-4 font-medium text-sm">Name</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Columns</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Rows</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {dataStores.map((store) => (
                <tr key={store.id} className="hover:bg-primary/5 transition-colors">
                  <td className="py-3 px-4">
                    <button
                      onClick={() => navigate(`/data-stores/${store.id}`)}
                      className="font-medium hover:text-primary"
                    >
                      {store.name}
                    </button>
                    {store.description && (
                      <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                        {store.description}
                      </p>
                    )}
                  </td>
                  <td className="py-3 px-4 text-sm">{store.schemaDefinition.length}</td>
                  <td className="py-3 px-4 text-sm">{store.rowCount}</td>
                  <td className="py-3 px-4 text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(store.createdAt), { addSuffix: true })}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => navigate(`/data-stores/${store.id}`)}
                        >
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleDelete(store)}
                          className="text-red-600"
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DataStoreCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={handleCreate}
        extractionSchemas={extractionSchemas}
      />
    </div>
  )
}
