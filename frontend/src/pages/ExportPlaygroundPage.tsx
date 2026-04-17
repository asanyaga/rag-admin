// frontend/src/pages/ExportPlaygroundPage.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'
import { AlignLeft, Play, RotateCcw, Eye, Save, SaveAll, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStores } from '@/hooks/useDataStores'
import { useExportMappings } from '@/hooks/useExportMappings'
import { FieldMappingEditor } from '@/components/export/FieldMappingEditor'
import { FanOutPreview } from '@/components/export/FanOutPreview'
import * as dataStoresApi from '@/api/dataStores'
import type { MappingEntry } from '@/components/export/FieldMappingEditor'
import type { ColumnDefinition } from '@/types/dataStore'

export default function ExportPlaygroundPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null
  const { dataStores } = useDataStores(projectId)

  const [selectedStoreId, setSelectedStoreId] = useState<string>('')
  const [sourceJson, setSourceJson] = useState('')
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [mapping, setMapping] = useState<MappingEntry[]>([])
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[] | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isExecuteLoading, setIsExecuteLoading] = useState(false)

  // Persistence state
  const [activeMappingId, setActiveMappingId] = useState<string | null>(null)
  const [activeMappingName, setActiveMappingName] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [saveAsName, setSaveAsName] = useState('')
  const [renameName, setRenameName] = useState('')
  const [isSaveAsOpen, setIsSaveAsOpen] = useState(false)
  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [isDeleteConfirm, setIsDeleteConfirm] = useState(false)

  const { mappings: savedMappings, create, update, remove } = useExportMappings(
    projectId,
    selectedStoreId || null
  )

  const selectedStore = dataStores.find((s) => s.id === selectedStoreId)
  const columns: ColumnDefinition[] = selectedStore?.schemaDefinition || []

  const validateJson = (value: string) => {
    if (!value.trim()) { setJsonError(null); return }
    try { JSON.parse(value); setJsonError(null) }
    catch { setJsonError('Invalid JSON') }
  }

  const formatJson = () => {
    try {
      setSourceJson(JSON.stringify(JSON.parse(sourceJson), null, 2))
      setJsonError(null)
    } catch { setJsonError('Cannot format — invalid JSON') }
  }

  const buildFieldMapping = (): Record<string, string> => {
    const result: Record<string, string> = {}
    for (const entry of mapping) {
      if (entry.sourcePath && entry.destinationColumn) {
        result[entry.sourcePath] = entry.destinationColumn
      }
    }
    return result
  }

  const handleMappingChange = (newMapping: MappingEntry[]) => {
    setMapping(newMapping)
    if (activeMappingId) setIsDirty(true)
  }

  // Load a saved mapping
  const handleLoad = (mappingId: string) => {
    const saved = savedMappings.find((m) => m.id === mappingId)
    if (!saved) return
    setMapping(saved.fieldMapping)
    setActiveMappingId(saved.id)
    setActiveMappingName(saved.name)
    setIsDirty(false)
  }

  // Save (overwrite) the currently loaded mapping
  const handleSave = async () => {
    if (!activeMappingId || !projectId) return
    try {
      await update(activeMappingId, { fieldMapping: mapping })
      setIsDirty(false)
      toast.success('Mapping saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    }
  }

  // Save As (create new)
  const handleSaveAs = async () => {
    if (!projectId || !selectedStoreId || !saveAsName.trim()) return
    try {
      const saved = await create({ dataStoreId: selectedStoreId, name: saveAsName.trim(), fieldMapping: mapping })
      setActiveMappingId(saved.id)
      setActiveMappingName(saved.name)
      setIsDirty(false)
      setSaveAsName('')
      setIsSaveAsOpen(false)
      toast.success(`Saved as "${saved.name}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    }
  }

  // Rename the loaded mapping
  const handleRename = async () => {
    if (!activeMappingId || !projectId || !renameName.trim()) return
    try {
      const updated = await update(activeMappingId, { name: renameName.trim() })
      setActiveMappingName(updated.name)
      setRenameName('')
      setIsRenameOpen(false)
      toast.success(`Renamed to "${updated.name}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rename failed')
    }
  }

  // Delete the loaded mapping
  const handleDelete = async () => {
    if (!activeMappingId || !projectId) return
    try {
      await remove(activeMappingId)
      setActiveMappingId(null)
      setActiveMappingName(null)
      setIsDirty(false)
      setIsDeleteConfirm(false)
      toast.success('Mapping deleted')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  const handlePreview = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsPreviewLoading(true)
    setPreviewError(null)
    setPreviewRows(null)
    try {
      const result = await dataStoresApi.previewExport(projectId, selectedStoreId, {
        sourceData: JSON.parse(sourceJson),
        fieldMapping: buildFieldMapping(),
      })
      setPreviewRows(result.rows)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Preview failed')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsExecuteLoading(true)
    try {
      const result = await dataStoresApi.executeExport(projectId, selectedStoreId, {
        sourceData: JSON.parse(sourceJson),
        fieldMapping: buildFieldMapping(),
      })
      toast.success(`Exported ${result.rowsImported} rows`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExecuteLoading(false)
    }
  }

  const handleClear = () => {
    setSourceJson('')
    setJsonError(null)
    setMapping([])
    setPreviewRows(null)
    setPreviewError(null)
    setActiveMappingId(null)
    setActiveMappingName(null)
    setIsDirty(false)
  }

  // When store changes, clear loaded mapping
  const handleStoreChange = (storeId: string) => {
    setSelectedStoreId(storeId)
    setActiveMappingId(null)
    setActiveMappingName(null)
    setIsDirty(false)
    setMapping([])
  }

  if (!projectId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Select a project to use the Export Playground.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Export Playground</h1>
        <p className="text-muted-foreground">Test field mappings and preview array fan-out before exporting</p>
      </div>

      {/* Section 1: Destination */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Destination Data Store</Label>
        <Select value={selectedStoreId} onValueChange={handleStoreChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select a data store" />
          </SelectTrigger>
          <SelectContent>
            {dataStores.map((store) => (
              <SelectItem key={store.id} value={store.id}>
                {store.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {columns.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {columns.map((col) => (
              <Badge key={col.name} variant="secondary" className="font-mono text-xs">
                {col.name}: {col.type}{!col.nullable && ' *'}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Section 2: Source Data */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Source Data (JSON)</Label>
          <Button variant="outline" size="sm" onClick={formatJson} disabled={!sourceJson.trim()}>
            <AlignLeft className="h-4 w-4 mr-1" /> Format
          </Button>
        </div>
        <Textarea
          value={sourceJson}
          onChange={(e) => setSourceJson(e.target.value)}
          onBlur={() => validateJson(sourceJson)}
          placeholder='{"receipt_date": "2026-04-15", "vendor": "Costco", "items": [{"description": "Bread", "price": 2.50}]}'
          rows={8}
          className={`font-mono text-sm ${jsonError ? 'border-red-500' : ''}`}
        />
        {jsonError && <p className="text-sm text-red-500">{jsonError}</p>}
      </div>

      <Separator />

      {/* Section 3: Field Mapping */}
      {selectedStoreId && (
        <div className="space-y-3">
          {/* Persistence toolbar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Saved Mappings</span>
              {isDirty && activeMappingId && (
                <span className="text-xs text-muted-foreground">(modified)</span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {/* Load */}
              <Select
                value={activeMappingId || ''}
                onValueChange={handleLoad}
                disabled={savedMappings.length === 0}
              >
                <SelectTrigger className="h-8 text-xs w-44">
                  <SelectValue placeholder="Load saved mapping" />
                </SelectTrigger>
                <SelectContent>
                  {savedMappings.map((m) => (
                    <SelectItem key={m.id} value={m.id} className="text-xs">
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Save (overwrite) */}
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={handleSave}
                disabled={!activeMappingId || !isDirty}
                title="Save changes to current mapping"
              >
                <Save className="h-3.5 w-3.5 mr-1" /> Save
              </Button>

              {/* Save As */}
              <Popover open={isSaveAsOpen} onOpenChange={setIsSaveAsOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={mapping.length === 0}
                    title="Save as new mapping"
                  >
                    <SaveAll className="h-3.5 w-3.5 mr-1" /> Save As
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-3" align="end">
                  <div className="space-y-2">
                    <p className="text-xs font-medium">Save mapping as</p>
                    <Input
                      value={saveAsName}
                      onChange={(e) => setSaveAsName(e.target.value)}
                      placeholder="e.g. Receipt extractor"
                      className="text-xs h-8"
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveAs()}
                      autoFocus
                    />
                    <Button
                      size="sm"
                      className="w-full h-7 text-xs"
                      onClick={handleSaveAs}
                      disabled={!saveAsName.trim()}
                    >
                      Save
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>

              {/* Rename */}
              <Popover open={isRenameOpen} onOpenChange={(open) => {
                setIsRenameOpen(open)
                if (open) setRenameName(activeMappingName || '')
              }}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={!activeMappingId}
                    title="Rename current mapping"
                  >
                    <Pencil className="h-3.5 w-3.5 mr-1" /> Rename
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-3" align="end">
                  <div className="space-y-2">
                    <p className="text-xs font-medium">Rename mapping</p>
                    <Input
                      value={renameName}
                      onChange={(e) => setRenameName(e.target.value)}
                      className="text-xs h-8"
                      onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                      autoFocus
                    />
                    <Button
                      size="sm"
                      className="w-full h-7 text-xs"
                      onClick={handleRename}
                      disabled={!renameName.trim() || renameName.trim() === activeMappingName}
                    >
                      Rename
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>

              {/* Delete */}
              {isDeleteConfirm ? (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground">Delete?</span>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={handleDelete}
                  >
                    Yes
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => setIsDeleteConfirm(false)}
                  >
                    No
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setIsDeleteConfirm(true)}
                  disabled={!activeMappingId}
                  title="Delete current mapping"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              )}
            </div>
          </div>

          <FieldMappingEditor
            sourceJson={sourceJson}
            destinationColumns={columns}
            mapping={mapping}
            onChange={handleMappingChange}
          />
        </div>
      )}

      <Separator />

      {/* Section 4: Preview & Execute */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <Button
            onClick={handlePreview}
            disabled={!selectedStoreId || !sourceJson.trim() || mapping.length === 0 || isPreviewLoading}
          >
            <Eye className="h-4 w-4 mr-1" />
            {isPreviewLoading ? 'Previewing...' : 'Preview'}
          </Button>
          <Button
            variant="default"
            onClick={handleExecute}
            disabled={!previewRows || previewRows.length === 0 || isExecuteLoading}
          >
            <Play className="h-4 w-4 mr-1" />
            {isExecuteLoading ? 'Exporting...' : 'Execute'}
          </Button>
          <Button variant="outline" onClick={handleClear}>
            <RotateCcw className="h-4 w-4 mr-1" /> Clear
          </Button>
        </div>

        {previewError && (
          <Alert variant="destructive">
            <AlertDescription>{previewError}</AlertDescription>
          </Alert>
        )}

        {previewRows && (
          <FanOutPreview rows={previewRows} columns={columns} />
        )}
      </div>
    </div>
  )
}
