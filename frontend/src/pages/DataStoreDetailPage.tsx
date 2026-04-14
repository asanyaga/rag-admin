import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, Upload, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStoreRows } from '@/hooks/useDataStoreRows'
import { DataGrid } from '@/components/data-stores/DataGrid'
import { AddRowDialog } from '@/components/data-stores/AddRowDialog'
import { CsvImportDialog } from '@/components/data-stores/CsvImportDialog'
import { DataStoreEditDialog } from '@/components/data-stores/DataStoreEditDialog'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStore, DataStoreUpdate } from '@/types/dataStore'

export default function DataStoreDetailPage() {
  const { storeId } = useParams<{ storeId: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null
  const navigate = useNavigate()

  const [store, setStore] = useState<DataStore | null>(null)
  const [storeLoading, setStoreLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)

  const [addRowOpen, setAddRowOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)

  const {
    rows,
    total,
    isLoading: rowsLoading,
    error: rowsError,
    page,
    setPage,
    pageSize,
    fetchRows,
    insertRow,
    updateRow,
    deleteRow,
    importCsv,
  } = useDataStoreRows(projectId, storeId || null)

  useEffect(() => {
    if (!projectId || !storeId) return
    setStoreLoading(true)
    dataStoresApi
      .getDataStore(projectId, storeId)
      .then(setStore)
      .catch((err) => setStoreError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setStoreLoading(false))
  }, [projectId, storeId])

  const handleAddRow = async (data: Record<string, unknown>) => {
    await insertRow(data)
    toast.success('Row added')
  }

  const handleUpdateRow = async (rowId: string, data: Record<string, unknown>) => {
    await updateRow(rowId, data)
    toast.success('Row updated')
  }

  const handleDeleteRow = async (rowId: string) => {
    await deleteRow(rowId)
    toast.success('Row deleted')
  }

  const handleImport = async (file: File, mapping: Record<string, string>) => {
    const result = await importCsv(file, mapping)
    toast.success(`Imported ${result.rowsImported} rows`)
    return result
  }

  const handleEditStore = async (id: string, data: DataStoreUpdate) => {
    if (!projectId) return
    const updated = await dataStoresApi.updateDataStore(projectId, id, data)
    setStore(updated)
    toast.success('Data store updated')
    await fetchRows()
  }

  const handleDeleteStore = async () => {
    if (!projectId || !storeId) return
    await dataStoresApi.deleteDataStore(projectId, storeId)
    toast.success('Data store deleted')
    navigate('/data-stores')
  }

  if (storeLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (storeError || !store) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{storeError || 'Data store not found'}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/data-stores')}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{store.name}</h1>
            {store.description && (
              <p className="text-muted-foreground">{store.description}</p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4 mr-1" /> Edit
          </Button>
          <Button variant="outline" size="sm" onClick={handleDeleteStore} className="text-red-600">
            <Trash2 className="h-4 w-4 mr-1" /> Delete
          </Button>
        </div>
      </div>

      {/* Schema summary */}
      <div className="flex flex-wrap gap-2">
        {store.schemaDefinition.map((col) => (
          <Badge key={col.name} variant="secondary" className="font-mono text-xs">
            {col.name}: {col.type}
            {!col.nullable && ' *'}
          </Badge>
        ))}
      </div>

      {/* Data actions */}
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setAddRowOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Row
        </Button>
        <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
          <Upload className="h-4 w-4 mr-1" /> Import CSV
        </Button>
      </div>

      {rowsError && (
        <Alert variant="destructive">
          <AlertDescription>{rowsError}</AlertDescription>
        </Alert>
      )}

      {/* Data grid */}
      {rowsLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <DataGrid
          columns={store.schemaDefinition}
          rows={rows}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onUpdateRow={handleUpdateRow}
          onDeleteRow={handleDeleteRow}
        />
      )}

      {/* Dialogs */}
      <AddRowDialog
        open={addRowOpen}
        onOpenChange={setAddRowOpen}
        columns={store.schemaDefinition}
        onAdd={handleAddRow}
      />
      <CsvImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        columns={store.schemaDefinition}
        onImport={handleImport}
      />
      <DataStoreEditDialog
        store={store}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSave={handleEditStore}
      />
    </div>
  )
}
