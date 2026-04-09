import { useState, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import {
  Upload,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  X,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'

interface CsvImportModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  schemaDefinition: Record<string, unknown>
  onImport: (records: Record<string, unknown>[]) => void
}

type Step = 'upload' | 'preview'

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB
const MAX_ROWS = 5000

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
          i++
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

type FieldSchema = { type?: string }

function getSchemaFields(
  schemaDefinition: Record<string, unknown>
): Record<string, FieldSchema> {
  const properties = (schemaDefinition.properties ?? {}) as Record<string, FieldSchema>
  return properties
}

function convertValue(value: string, fieldSchema: FieldSchema): unknown {
  if (value === '') return ''
  if (fieldSchema.type === 'number') {
    const num = parseFloat(value)
    return isNaN(num) ? value : num
  }
  return value
}

interface ParsedRecord {
  row: number
  data: Record<string, unknown>
}

interface ParseError {
  row: number
  message: string
}

interface ParseResult {
  records: ParsedRecord[]
  errors: ParseError[]
  warnings: string[]
  totalRows: number
  columns: string[]
}

function parseCsv(
  text: string,
  schemaDefinition: Record<string, unknown>
): ParseResult {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '')
  if (lines.length === 0) {
    return { records: [], errors: [{ row: 0, message: 'File is empty' }], warnings: [], totalRows: 0, columns: [] }
  }

  const headers = parseCsvLine(lines[0]).map((h) => h.trim())
  const fields = getSchemaFields(schemaDefinition)
  const fieldKeys = Object.keys(fields)

  // Check that at least one column matches a schema field
  const matchedColumns = headers.filter((h) => fieldKeys.includes(h))
  if (matchedColumns.length === 0) {
    return {
      records: [],
      errors: [{ row: 0, message: `No columns match schema fields. Expected: ${fieldKeys.join(', ')}` }],
      warnings: [],
      totalRows: lines.length - 1,
      columns: headers,
    }
  }

  const unknownColumns = headers.filter((h) => !fieldKeys.includes(h))
  const warnings: string[] = []
  if (unknownColumns.length > 0) {
    warnings.push(`Unknown columns ignored: ${unknownColumns.join(', ')}`)
  }

  const missingColumns = fieldKeys.filter((k) => !headers.includes(k))
  if (missingColumns.length > 0) {
    warnings.push(`Missing schema fields (will be empty): ${missingColumns.join(', ')}`)
  }

  const dataRows = lines.slice(1)
  if (dataRows.length > MAX_ROWS) {
    return {
      records: [],
      errors: [{ row: 0, message: `Too many rows (${dataRows.length}). Maximum is ${MAX_ROWS}.` }],
      warnings,
      totalRows: dataRows.length,
      columns: matchedColumns,
    }
  }

  const records: ParsedRecord[] = []
  const errors: ParseError[] = []

  for (let i = 0; i < dataRows.length; i++) {
    const rowNum = i + 2
    const values = parseCsvLine(dataRows[i])

    const data: Record<string, unknown> = {}
    let rowError: string | null = null

    for (const key of fieldKeys) {
      const colIndex = headers.indexOf(key)
      if (colIndex === -1) continue
      const rawValue = values[colIndex]?.trim() ?? ''
      if (rawValue === '') continue
      try {
        data[key] = convertValue(rawValue, fields[key])
      } catch {
        rowError = `Failed to parse field "${key}"`
        break
      }
    }

    if (rowError) {
      errors.push({ row: rowNum, message: rowError })
      continue
    }

    // Skip completely empty rows
    if (Object.keys(data).length === 0) continue

    records.push({ row: rowNum, data })
  }

  return { records, errors, warnings, totalRows: dataRows.length, columns: matchedColumns }
}

function generateTemplate(schemaDefinition: Record<string, unknown>): string {
  const fields = getSchemaFields(schemaDefinition)
  const keys = Object.keys(fields)
  const headers = keys.join(',')

  const exampleValues = keys.map((key) => {
    if (fields[key].type === 'number') return '0'
    return ''
  })

  return headers + '\n' + exampleValues.join(',')
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CsvImportModal({
  open,
  onOpenChange,
  schemaDefinition,
  onImport,
}: CsvImportModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = useCallback(() => {
    setStep('upload')
    setFile(null)
    setParseResult(null)
    setParseError(null)
    setParsing(false)
  }, [])

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) reset()
    onOpenChange(nextOpen)
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
      const result = parseCsv(text, schemaDefinition)

      if (result.records.length === 0 && result.errors.length > 0 && result.errors[0].row === 0) {
        setParseError(result.errors[0].message)
        return
      }

      setParseResult(result)
      setStep('preview')
    } catch {
      setParseError('Failed to read file')
    } finally {
      setParsing(false)
    }
  }

  const handleImport = () => {
    if (!parseResult) return
    const records = parseResult.records.map((r) => r.data)
    onImport(records)
    handleOpenChange(false)
  }

  const downloadTemplate = () => {
    const csv = generateTemplate(schemaDefinition)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'expected_output_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const fields = getSchemaFields(schemaDefinition)
  const fieldKeys = Object.keys(fields)

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Import Expected Output from CSV</DialogTitle>
          <DialogDescription>
            {step === 'upload' && 'Upload a CSV where each row is a record and columns match the schema fields.'}
            {step === 'preview' && 'Review the parsed records before importing.'}
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
                      Columns: {fieldKeys.join(', ')}
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
            {/* Summary */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary">
                {parseResult.records.length} records
              </Badge>
              {parseResult.errors.length > 0 && (
                <Badge variant="destructive">
                  {parseResult.errors.length} errors
                </Badge>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {parseResult.totalRows} rows parsed &middot; {parseResult.columns.length} fields matched
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

            {/* Data table */}
            <ScrollArea className="flex-1 max-h-[400px] border rounded-lg">
              <div className="min-w-0">
                {/* Table header */}
                <div className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm border-b px-3 py-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span className="w-8 text-center shrink-0">#</span>
                  {parseResult.columns.map((col) => (
                    <span key={col} className="flex-1 min-w-[80px] truncate capitalize">
                      {col.replace(/_/g, ' ')}
                    </span>
                  ))}
                  <span className="w-10 text-center shrink-0">Status</span>
                </div>

                {/* Valid records */}
                {parseResult.records.map((record) => (
                  <div
                    key={record.row}
                    className="flex items-center gap-2 px-3 py-2 border-b text-sm hover:bg-muted/50"
                  >
                    <span className="w-8 text-center text-xs text-muted-foreground shrink-0">
                      {record.row}
                    </span>
                    {parseResult.columns.map((col) => (
                      <span key={col} className="flex-1 min-w-[80px] text-xs truncate">
                        {String(record.data[col] ?? '')}
                      </span>
                    ))}
                    <span className="w-10 flex justify-center shrink-0">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    </span>
                  </div>
                ))}

                {/* Error rows */}
                {parseResult.errors.map((err, i) => (
                  <div
                    key={`err-${i}`}
                    className="flex items-center gap-2 px-3 py-2 border-b text-sm opacity-60"
                  >
                    <span className="w-8 text-center text-xs text-muted-foreground shrink-0">
                      {err.row}
                    </span>
                    <span className="flex-1 text-xs text-destructive truncate">
                      {err.message}
                    </span>
                    <span className="w-10 flex justify-center shrink-0">
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
                disabled={parseResult.records.length === 0}
              >
                Import {parseResult.records.length} {parseResult.records.length === 1 ? 'record' : 'records'}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
