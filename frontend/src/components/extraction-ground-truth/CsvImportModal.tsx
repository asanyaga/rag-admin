import { useState, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import {
  Upload,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Copy,
  X,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import * as api from '@/api/extractionGroundTruth'
import type {
  CsvParseResult,
  CsvParsedRow,
  CsvParseError,
  BulkImportResponse,
} from '@/types/extractionGroundTruth'

interface CsvImportModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  setId: string
  schemaDefinition: Record<string, unknown>
  existingDocumentIds: Set<string>
  onImportComplete: () => void
}

type Step = 'upload' | 'preview' | 'result'

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB
const MAX_ROWS = 5000
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ANNOTATION_COLUMNS = ['annotation_quality', 'annotation_difficulty', 'annotation_notes']

// ---------------------------------------------------------------------------
// CSV Parsing Helpers
// ---------------------------------------------------------------------------

function parseCsvLine(line: string): string[] {
  const fields: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"'
          i++ // skip escaped quote
        } else {
          inQuotes = false
        }
      } else {
        current += ch
      }
    } else {
      if (ch === '"') {
        inQuotes = true
      } else if (ch === ',') {
        fields.push(current)
        current = ''
      } else {
        current += ch
      }
    }
  }
  fields.push(current)
  return fields
}

function getSchemaProperties(
  schemaDefinition: Record<string, unknown>
): Record<string, { type?: string; items?: { properties?: Record<string, { type?: string }> } }> {
  return (schemaDefinition.properties ?? {}) as Record<
    string,
    { type?: string; items?: { properties?: Record<string, { type?: string }> } }
  >
}

function convertFieldValue(
  value: string,
  fieldSchema: { type?: string; items?: { properties?: Record<string, { type?: string }> } }
): unknown {
  if (value === '') return ''

  if (fieldSchema.type === 'number') {
    const num = parseFloat(value)
    return isNaN(num) ? value : num
  }

  if (fieldSchema.type === 'array') {
    return JSON.parse(value) // caller catches parse errors
  }

  return value
}

function parseCsv(
  text: string,
  schemaDefinition: Record<string, unknown>,
  existingDocumentIds: Set<string>
): CsvParseResult {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '')
  if (lines.length === 0) {
    return { validRows: [], errors: [{ row: 0, message: 'File is empty' }], duplicateRows: [], warnings: [], totalRows: 0 }
  }

  const headers = parseCsvLine(lines[0]).map((h) => h.trim())
  const docIdIndex = headers.findIndex((h) => h === 'document_id')
  if (docIdIndex === -1) {
    return {
      validRows: [],
      errors: [{ row: 0, message: 'Missing required column: document_id' }],
      duplicateRows: [],
      warnings: [],
      totalRows: lines.length - 1,
    }
  }

  const properties = getSchemaProperties(schemaDefinition)
  const schemaKeys = Object.keys(properties)
  const knownColumns = new Set(['document_id', ...schemaKeys, ...ANNOTATION_COLUMNS])
  const unknownColumns = headers.filter((h) => !knownColumns.has(h))
  const warnings: string[] = []
  if (unknownColumns.length > 0) {
    warnings.push(`Unknown columns will be ignored: ${unknownColumns.join(', ')}`)
  }

  const dataRows = lines.slice(1)
  if (dataRows.length > MAX_ROWS) {
    return {
      validRows: [],
      errors: [{ row: 0, message: `Too many rows (${dataRows.length}). Maximum is ${MAX_ROWS}.` }],
      duplicateRows: [],
      warnings,
      totalRows: dataRows.length,
    }
  }

  const validRows: CsvParsedRow[] = []
  const errors: CsvParseError[] = []
  const duplicateRows: CsvParsedRow[] = []
  const seenDocIds = new Set<string>()

  for (let i = 0; i < dataRows.length; i++) {
    const rowNum = i + 2 // 1-indexed, skip header
    const fields = parseCsvLine(dataRows[i])
    const documentId = fields[docIdIndex]?.trim() ?? ''

    if (!documentId) {
      errors.push({ row: rowNum, message: 'Empty document_id' })
      continue
    }

    if (!UUID_RE.test(documentId)) {
      errors.push({ row: rowNum, message: `Invalid UUID: ${documentId}` })
      continue
    }

    if (seenDocIds.has(documentId)) {
      errors.push({ row: rowNum, message: `Duplicate document_id in file: ${documentId}` })
      continue
    }
    seenDocIds.add(documentId)

    // Build expectedData
    const expectedData: Record<string, unknown> = {}
    let rowError: string | null = null

    for (const key of schemaKeys) {
      const colIndex = headers.indexOf(key)
      if (colIndex === -1) continue
      const rawValue = fields[colIndex]?.trim() ?? ''
      if (rawValue === '') continue
      try {
        expectedData[key] = convertFieldValue(rawValue, properties[key])
      } catch {
        rowError = `Failed to parse field "${key}": invalid value`
        break
      }
    }

    if (rowError) {
      errors.push({ row: rowNum, message: rowError })
      continue
    }

    // Build annotations
    let annotations: Record<string, unknown> | null = null
    for (const col of ANNOTATION_COLUMNS) {
      const colIndex = headers.indexOf(col)
      if (colIndex === -1) continue
      const val = fields[colIndex]?.trim() ?? ''
      if (!val) continue
      if (!annotations) annotations = {}
      const annotKey = col.replace('annotation_', '')
      annotations[annotKey] = val
    }

    const parsed: CsvParsedRow = { row: rowNum, documentId, expectedData, annotations }

    if (existingDocumentIds.has(documentId)) {
      duplicateRows.push(parsed)
    } else {
      validRows.push(parsed)
    }
  }

  return { validRows, errors, duplicateRows, warnings, totalRows: dataRows.length }
}

function generateTemplate(schemaDefinition: Record<string, unknown>): string {
  const properties = getSchemaProperties(schemaDefinition)
  const schemaKeys = Object.keys(properties)
  const headers = ['document_id', ...schemaKeys, ...ANNOTATION_COLUMNS]

  const exampleValues = ['00000000-0000-0000-0000-000000000000']
  for (const key of schemaKeys) {
    const prop = properties[key]
    if (prop.type === 'number') {
      exampleValues.push('0')
    } else if (prop.type === 'array' && prop.items?.properties) {
      const itemKeys = Object.keys(prop.items.properties)
      const example = itemKeys.reduce<Record<string, string>>((acc, k) => {
        acc[k] = prop.items!.properties![k].type === 'number' ? '0' : ''
        return acc
      }, {})
      exampleValues.push(`"${JSON.stringify([example]).replace(/"/g, '""')}"`)
    } else {
      exampleValues.push('')
    }
  }
  exampleValues.push('clean', 'easy', '')

  return headers.join(',') + '\n' + exampleValues.join(',')
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CsvImportModal({
  open,
  onOpenChange,
  setId,
  schemaDefinition,
  existingDocumentIds,
  onImportComplete,
}: CsvImportModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [parseResult, setParseResult] = useState<CsvParseResult | null>(null)
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [importResult, setImportResult] = useState<BulkImportResponse | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = useCallback(() => {
    setStep('upload')
    setFile(null)
    setParsing(false)
    setImporting(false)
    setParseResult(null)
    setSelectedRows(new Set())
    setImportResult(null)
    setParseError(null)
  }, [])

  const handleOpenChange = (open: boolean) => {
    if (!open) reset()
    onOpenChange(open)
  }

  const handleFileSelect = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase()
    if (ext !== 'csv') {
      toast.error('Please select a .csv file')
      return
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      toast.error('File too large. Maximum size is 10 MB.')
      return
    }
    setFile(selectedFile)
    setParseError(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) handleFileSelect(droppedFile)
  }

  const handleParse = async () => {
    if (!file) return
    setParsing(true)
    setParseError(null)
    try {
      const text = await file.text()
      const result = parseCsv(text, schemaDefinition, existingDocumentIds)

      // Check for file-level errors (no document_id column, empty file, too many rows)
      if (result.validRows.length === 0 && result.duplicateRows.length === 0 && result.errors.length > 0 && result.errors[0].row === 0) {
        setParseError(result.errors[0].message)
        return
      }

      setParseResult(result)
      setSelectedRows(new Set(result.validRows.map((_, i) => i)))
      setStep('preview')
    } catch {
      setParseError('Failed to read file')
    } finally {
      setParsing(false)
    }
  }

  const handleImport = async () => {
    if (!parseResult) return
    setImporting(true)
    try {
      const items = parseResult.validRows
        .filter((_, i) => selectedRows.has(i))
        .map((row) => ({
          documentId: row.documentId,
          expectedData: row.expectedData,
          annotations: row.annotations ?? undefined,
        }))

      const result = await api.bulkCreateGroundTruthItems(setId, { items })
      setImportResult(result)
      setStep('result')
    } catch {
      toast.error('Import failed. Please try again.')
    } finally {
      setImporting(false)
    }
  }

  const handleDone = () => {
    onImportComplete()
    handleOpenChange(false)
  }

  const toggleRow = (index: number) => {
    setSelectedRows((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const toggleAll = () => {
    if (!parseResult) return
    if (selectedRows.size === parseResult.validRows.length) {
      setSelectedRows(new Set())
    } else {
      setSelectedRows(new Set(parseResult.validRows.map((_, i) => i)))
    }
  }

  const downloadTemplate = () => {
    const csv = generateTemplate(schemaDefinition)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ground_truth_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const selectedCount = selectedRows.size

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Import Ground Truth from CSV</DialogTitle>
          <DialogDescription>
            {step === 'upload' && 'Upload a CSV file with document IDs and expected extraction values.'}
            {step === 'preview' && 'Review the parsed data before importing.'}
            {step === 'result' && 'Import complete.'}
          </DialogDescription>
        </DialogHeader>

        {/* Step 1: Upload */}
        {step === 'upload' && (
          <div className="space-y-4">
            <div
              className={`
                border-2 border-dashed rounded-lg p-8
                flex flex-col items-center gap-3 cursor-pointer
                transition-colors
                ${file ? 'border-primary/50 bg-primary/5' : 'border-muted-foreground/25 hover:border-muted-foreground/50'}
              `}
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) handleFileSelect(f)
                }}
              />
              {file ? (
                <>
                  <FileText className="h-8 w-8 text-primary" />
                  <div className="text-center">
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      setFile(null)
                      setParseError(null)
                    }}
                  >
                    <X className="mr-1 h-3 w-3" />
                    Remove
                  </Button>
                </>
              ) : (
                <>
                  <Upload className="h-8 w-8 text-muted-foreground" />
                  <div className="text-center">
                    <p className="text-sm font-medium">
                      Drop a CSV file here or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground">
                      .csv files up to 10 MB
                    </p>
                  </div>
                </>
              )}
            </div>

            {parseError && (
              <div className="flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3">
                <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                <p className="text-sm text-destructive">{parseError}</p>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Button variant="ghost" size="sm" onClick={downloadTemplate}>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Download template
              </Button>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleParse} disabled={!file || parsing}>
                {parsing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Parse File
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 2: Preview */}
        {step === 'preview' && parseResult && (
          <div className="flex flex-col gap-4 min-h-0">
            {/* Summary bar */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary">
                {parseResult.validRows.length} valid
              </Badge>
              {parseResult.errors.length > 0 && (
                <Badge variant="destructive">
                  {parseResult.errors.length} errors
                </Badge>
              )}
              {parseResult.duplicateRows.length > 0 && (
                <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                  {parseResult.duplicateRows.length} duplicates
                </Badge>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {parseResult.totalRows} total rows parsed
              </span>
            </div>

            {/* Warnings */}
            {parseResult.warnings.length > 0 && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800">
                  {parseResult.warnings.map((w, i) => (
                    <p key={i}>{w}</p>
                  ))}
                </div>
              </div>
            )}

            {/* Table */}
            <ScrollArea className="flex-1 max-h-[400px] border rounded-lg">
              <div className="min-w-0">
                {/* Header */}
                <div className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm border-b px-3 py-2 flex items-center gap-3 text-xs font-medium text-muted-foreground">
                  <Checkbox
                    checked={
                      parseResult.validRows.length > 0 &&
                      selectedRows.size === parseResult.validRows.length
                    }
                    onCheckedChange={toggleAll}
                    aria-label="Select all"
                  />
                  <span className="w-8 text-center">#</span>
                  <span className="w-56">Document ID</span>
                  <span className="flex-1">Fields</span>
                  <span className="w-14 text-center">Status</span>
                </div>

                {/* Valid rows */}
                {parseResult.validRows.map((row, i) => (
                  <ValidRow
                    key={i}
                    row={row}
                    selected={selectedRows.has(i)}
                    onToggle={() => toggleRow(i)}
                  />
                ))}

                {/* Duplicate rows */}
                {parseResult.duplicateRows.map((row, i) => (
                  <div
                    key={`dup-${i}`}
                    className="flex items-center gap-3 px-3 py-2 border-b text-sm opacity-60"
                  >
                    <Checkbox disabled checked={false} />
                    <span className="w-8 text-center text-xs text-muted-foreground">
                      {row.row}
                    </span>
                    <span className="w-56 text-xs font-mono truncate">{row.documentId}</span>
                    <span className="flex-1 text-xs text-muted-foreground">-</span>
                    <span className="w-14 flex justify-center">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>
                            <Copy className="h-3.5 w-3.5 text-amber-500" />
                          </TooltipTrigger>
                          <TooltipContent>Duplicate - document already in set</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </span>
                  </div>
                ))}

                {/* Error rows */}
                {parseResult.errors.map((err, i) => (
                  <div
                    key={`err-${i}`}
                    className="flex items-center gap-3 px-3 py-2 border-b text-sm opacity-60"
                  >
                    <Checkbox disabled checked={false} />
                    <span className="w-8 text-center text-xs text-muted-foreground">
                      {err.row}
                    </span>
                    <span className="w-56 text-xs text-destructive truncate">
                      {err.message}
                    </span>
                    <span className="flex-1" />
                    <span className="w-14 flex justify-center">
                      <AlertCircle className="h-3.5 w-3.5 text-destructive" />
                    </span>
                  </div>
                ))}
              </div>
            </ScrollArea>

            <DialogFooter>
              <Button variant="outline" onClick={() => { setStep('upload'); setParseResult(null) }}>
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={selectedCount === 0 || importing}
              >
                {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Import {selectedCount} {selectedCount === 1 ? 'item' : 'items'}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Result */}
        {step === 'result' && importResult && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-3 py-6">
              <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              <p className="text-lg font-medium">
                Imported {importResult.created} {importResult.created === 1 ? 'item' : 'items'}
              </p>
              {importResult.errors.length > 0 && (
                <div className="w-full max-w-md">
                  <p className="text-sm text-muted-foreground mb-2">
                    {importResult.errors.length} {importResult.errors.length === 1 ? 'error' : 'errors'}:
                  </p>
                  <ScrollArea className="max-h-32 border rounded-lg p-2">
                    {importResult.errors.map((err, i) => (
                      <p key={i} className="text-xs text-destructive">{err}</p>
                    ))}
                  </ScrollArea>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button onClick={handleDone}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ValidRow({
  row,
  selected,
  onToggle,
}: {
  row: CsvParsedRow
  selected: boolean
  onToggle: () => void
}) {
  const fieldCount = Object.keys(row.expectedData).length
  const annotationText = row.annotations
    ? Object.entries(row.annotations).map(([k, v]) => `${k}: ${v}`).join(', ')
    : null

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 border-b text-sm hover:bg-muted/50 transition-colors ${
        selected ? '' : 'opacity-50'
      }`}
    >
      <Checkbox checked={selected} onCheckedChange={onToggle} />
      <span className="w-8 text-center text-xs text-muted-foreground">
        {row.row}
      </span>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="w-56 text-xs font-mono truncate cursor-default">
              {row.documentId}
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom">{row.documentId}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex-1 text-xs text-muted-foreground truncate cursor-default">
              {fieldCount} fields{annotationText ? ` | ${annotationText}` : ''}
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-sm font-mono text-xs">
            {JSON.stringify(row.expectedData, null, 2).slice(0, 300)}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <span className="w-14 flex justify-center">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
      </span>
    </div>
  )
}
