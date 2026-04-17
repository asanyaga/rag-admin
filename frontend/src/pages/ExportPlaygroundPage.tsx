// frontend/src/pages/ExportPlaygroundPage.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { AlignLeft, Play, RotateCcw, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStores } from '@/hooks/useDataStores'
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

  const selectedStore = dataStores.find((s) => s.id === selectedStoreId)
  const columns: ColumnDefinition[] = selectedStore?.schemaDefinition || []

  const validateJson = (value: string) => {
    if (!value.trim()) {
      setJsonError(null)
      return
    }
    try {
      JSON.parse(value)
      setJsonError(null)
    } catch {
      setJsonError('Invalid JSON')
    }
  }

  const formatJson = () => {
    try {
      const parsed = JSON.parse(sourceJson)
      setSourceJson(JSON.stringify(parsed, null, 2))
      setJsonError(null)
    } catch {
      setJsonError('Cannot format — invalid JSON')
    }
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

  const handlePreview = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsPreviewLoading(true)
    setPreviewError(null)
    setPreviewRows(null)
    try {
      const parsed = JSON.parse(sourceJson)
      const fieldMapping = buildFieldMapping()
      const result = await dataStoresApi.previewExport(projectId, selectedStoreId, {
        sourceData: parsed,
        fieldMapping,
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
      const parsed = JSON.parse(sourceJson)
      const fieldMapping = buildFieldMapping()
      const result = await dataStoresApi.executeExport(projectId, selectedStoreId, {
        sourceData: parsed,
        fieldMapping,
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
        <Select value={selectedStoreId} onValueChange={setSelectedStoreId}>
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
                {col.name}: {col.type}
                {!col.nullable && ' *'}
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
        {jsonError && (
          <p className="text-sm text-red-500">{jsonError}</p>
        )}
      </div>

      <Separator />

      {/* Section 3: Field Mapping */}
      {selectedStoreId && (
        <FieldMappingEditor
          sourceJson={sourceJson}
          destinationColumns={columns}
          mapping={mapping}
          onChange={setMapping}
        />
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
