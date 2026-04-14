// frontend/src/components/data-stores/CsvImportDialog.tsx
import { useState, useCallback } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Upload } from 'lucide-react'
import type { ColumnDefinition, CsvImportResponse } from '@/types/dataStore'

interface CsvImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  columns: ColumnDefinition[]
  onImport: (file: File, columnMapping: Record<string, string>) => Promise<CsvImportResponse>
}

export function CsvImportDialog({ open, onOpenChange, columns, onImport }: CsvImportDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [previewRows, setPreviewRows] = useState<string[][]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [isImporting, setIsImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CsvImportResponse | null>(null)

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0]
      if (!selected) return

      setFile(selected)
      setError(null)
      setResult(null)

      const reader = new FileReader()
      reader.onload = (event) => {
        const text = event.target?.result as string
        const lines = text.split('\n').filter((l) => l.trim())
        if (lines.length === 0) {
          setError('CSV file is empty')
          return
        }

        const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''))
        setCsvHeaders(headers)

        const preview = lines.slice(1, 6).map((line) =>
          line.split(',').map((v) => v.trim().replace(/^"|"$/g, ''))
        )
        setPreviewRows(preview)

        // Auto-map by name match
        const autoMapping: Record<string, string> = {}
        const storeColNames = columns.map((c) => c.name)
        for (const header of headers) {
          const normalized = header.toLowerCase().replace(/\s+/g, '_')
          if (storeColNames.includes(normalized)) {
            autoMapping[header] = normalized
          }
        }
        setMapping(autoMapping)
      }
      reader.readAsText(selected)
    },
    [columns]
  )

  const handleImport = async () => {
    if (!file) return

    const activeMappings = Object.entries(mapping).filter(([, v]) => v !== '')
    if (activeMappings.length === 0) {
      setError('Map at least one column')
      return
    }

    // Check required columns
    const mappedStoreCols = new Set(activeMappings.map(([, v]) => v))
    for (const col of columns) {
      if (!col.nullable && !mappedStoreCols.has(col.name)) {
        setError(`Required column "${col.name}" is not mapped`)
        return
      }
    }

    setIsImporting(true)
    setError(null)
    try {
      const mappingObj = Object.fromEntries(activeMappings)
      const res = await onImport(file, mappingObj)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setIsImporting(false)
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setFile(null)
    setCsvHeaders([])
    setPreviewRows([])
    setMapping({})
    setError(null)
    setResult(null)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import CSV</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* File selector */}
          <div className="space-y-2">
            <Label>CSV File</Label>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 px-4 py-2 border rounded-md cursor-pointer hover:bg-muted/50 transition-colors">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{file ? file.name : 'Choose file...'}</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Column mapping */}
          {csvHeaders.length > 0 && (
            <div className="space-y-3">
              <Label>Column Mapping</Label>
              <div className="border rounded-md">
                <table className="w-full">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left py-2 px-3 text-sm font-medium">CSV Column</th>
                      <th className="text-left py-2 px-3 text-sm font-medium">→</th>
                      <th className="text-left py-2 px-3 text-sm font-medium">Store Column</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {csvHeaders.map((header) => (
                      <tr key={header}>
                        <td className="py-2 px-3 text-sm font-mono">{header}</td>
                        <td className="py-2 px-3 text-sm text-muted-foreground">→</td>
                        <td className="py-2 px-3">
                          <Select
                            value={mapping[header] || '_skip'}
                            onValueChange={(v) =>
                              setMapping((prev) => ({
                                ...prev,
                                [header]: v === '_skip' ? '' : v,
                              }))
                            }
                          >
                            <SelectTrigger className="h-8">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="_skip">— Skip —</SelectItem>
                              {columns.map((col) => (
                                <SelectItem key={col.name} value={col.name}>
                                  {col.name} ({col.type})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Preview */}
          {previewRows.length > 0 && (
            <div className="space-y-2">
              <Label>Preview (first {previewRows.length} rows)</Label>
              <div className="border rounded-md overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-muted/50">
                    <tr>
                      {csvHeaders.map((h) => (
                        <th key={h} className="py-1 px-2 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {previewRows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j} className="py-1 px-2">{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result && (
            <div className="text-sm text-green-600">
              Successfully imported {result.rowsImported} rows.
            </div>
          )}
          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            {result ? 'Close' : 'Cancel'}
          </Button>
          {!result && (
            <Button onClick={handleImport} disabled={!file || isImporting}>
              {isImporting ? 'Importing...' : 'Import'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
