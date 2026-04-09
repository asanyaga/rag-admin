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

/**
 * Parse an entire CSV string into rows of fields.
 * Handles multiline values inside quoted fields (RFC 4180).
 */
function parseCsvRows(text: string): string[][] {
  const rows: string[][] = []
  let current = ''
  let inQuotes = false
  let fields: string[] = []

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]

    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < text.length && text[i + 1] === '"') {
          current += '"'
          i++ // skip escaped quote
        } else {
          inQuotes = false
        }
      } else {
        // Include newlines inside quoted fields as part of the value
        current += ch
      }
    } else {
      if (ch === '"') {
        inQuotes = true
      } else if (ch === ',') {
        fields.push(current)
        current = ''
      } else if (ch === '\n' || ch === '\r') {
        // End of row (skip \r in \r\n)
        if (ch === '\r' && i + 1 < text.length && text[i + 1] === '\n') {
          i++
        }
        fields.push(current)
        current = ''
        // Skip empty rows (all fields empty)
        if (fields.some((f) => f.trim() !== '')) {
          rows.push(fields)
        }
        fields = []
      } else {
        current += ch
      }
    }
  }

  // Handle last row (no trailing newline)
  fields.push(current)
  if (fields.some((f) => f.trim() !== '')) {
    rows.push(fields)
  }

  return rows
}

type FieldSchema = { type?: string; items?: { properties?: Record<string, { type?: string }> } }

/**
 * Resolve the effective CSV columns from a schema definition.
 *
 * Two schema shapes:
 *  1. Scalar fields:  { properties: { invoice_number: {type:"string"}, total: {type:"number"} } }
 *     → columns are the top-level property keys, each row is a flat record.
 *  2. Array field:    { properties: { transactions: {type:"array", items:{properties:{receipt_number:{type:"string"}, ...}}} } }
 *     → columns are the *sub-properties* of the array items, each row is one array entry.
 *     The array field name is returned as `arrayFieldName` so we can wrap the result.
 */
interface ResolvedColumns {
  /** Column names that appear in the CSV header */
  columns: Record<string, { type?: string }>
  /** If the schema is an array-field schema, this is the parent field name (e.g. "transactions") */
  arrayFieldName: string | null
}

function resolveColumns(schemaDefinition: Record<string, unknown>): ResolvedColumns {
  const properties = (schemaDefinition.properties ?? {}) as Record<string, FieldSchema>
  const keys = Object.keys(properties)

  // Check if there's a single array field whose items have properties — flatten it
  const arrayFields = keys.filter(
    (k) => properties[k].type === 'array' && properties[k].items?.properties
  )

  if (arrayFields.length === 1 && keys.length === 1) {
    // Schema is a single array field — use sub-properties as columns
    const arrayKey = arrayFields[0]
    const subProps = properties[arrayKey].items!.properties!
    return {
      columns: subProps as Record<string, { type?: string }>,
      arrayFieldName: arrayKey,
    }
  }

  // Otherwise treat all top-level properties as columns (scalar fields)
  const cols: Record<string, { type?: string }> = {}
  for (const key of keys) {
    cols[key] = { type: properties[key].type }
  }
  return { columns: cols, arrayFieldName: null }
}

function convertValue(value: string, fieldType?: string): unknown {
  if (value === '') return ''
  if (fieldType === 'number') {
    // Strip thousands separators (commas) before parsing, e.g. "30,000.00" → "30000.00"
    const cleaned = value.replace(/,/g, '')
    const num = parseFloat(cleaned)
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
  arrayFieldName: string | null
}

function parseCsv(
  text: string,
  schemaDefinition: Record<string, unknown>
): ParseResult {
  const allRows = parseCsvRows(text)
  if (allRows.length === 0) {
    return { records: [], errors: [{ row: 0, message: 'File is empty' }], warnings: [], totalRows: 0, columns: [], arrayFieldName: null }
  }

  const headers = allRows[0].map((h) => h.trim())
  const { columns, arrayFieldName } = resolveColumns(schemaDefinition)
  const columnKeys = Object.keys(columns)

  // Check that at least one column matches
  const matchedColumns = headers.filter((h) => columnKeys.includes(h))
  if (matchedColumns.length === 0) {
    return {
      records: [],
      errors: [{ row: 0, message: `No columns match schema fields. Expected: ${columnKeys.join(', ')}` }],
      warnings: [],
      totalRows: allRows.length - 1,
      columns: headers,
      arrayFieldName,
    }
  }

  const unknownColumns = headers.filter((h) => !columnKeys.includes(h))
  const warnings: string[] = []
  if (unknownColumns.length > 0) {
    warnings.push(`Unknown columns ignored: ${unknownColumns.join(', ')}`)
  }

  const missingColumns = columnKeys.filter((k) => !headers.includes(k))
  if (missingColumns.length > 0) {
    warnings.push(`Missing schema fields (will be empty): ${missingColumns.join(', ')}`)
  }

  const dataRows = allRows.slice(1)
  if (dataRows.length > MAX_ROWS) {
    return {
      records: [],
      errors: [{ row: 0, message: `Too many rows (${dataRows.length}). Maximum is ${MAX_ROWS}.` }],
      warnings,
      totalRows: dataRows.length,
      columns: matchedColumns,
      arrayFieldName,
    }
  }

  const records: ParsedRecord[] = []
  const errors: ParseError[] = []

  for (let i = 0; i < dataRows.length; i++) {
    const rowNum = i + 2
    const values = dataRows[i]

    const data: Record<string, unknown> = {}
    let rowError: string | null = null

    for (const key of columnKeys) {
      const colIndex = headers.indexOf(key)
      if (colIndex === -1) continue
      const rawValue = values[colIndex]?.trim() ?? ''
      if (rawValue === '') continue
      try {
        data[key] = convertValue(rawValue, columns[key].type)
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

  return { records, errors, warnings, totalRows: dataRows.length, columns: matchedColumns, arrayFieldName }
}

function generateTemplate(schemaDefinition: Record<string, unknown>): string {
  const { columns } = resolveColumns(schemaDefinition)
  const keys = Object.keys(columns)
  const headers = keys.join(',')

  const exampleValues = keys.map((key) => {
    if (columns[key].type === 'number') return '0'
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
    const rows = parseResult.records.map((r) => r.data)

    if (parseResult.arrayFieldName) {
      // Array schema: wrap rows under the array field name
      // e.g. { transactions: [row1, row2, ...] }
      onImport([{ [parseResult.arrayFieldName]: rows }])
    } else {
      onImport(rows)
    }
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

  const { columns: resolvedCols } = resolveColumns(schemaDefinition)
  const columnKeys = Object.keys(resolvedCols)

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
                      Columns: {columnKeys.join(', ')}
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

            {/* Data table — horizontally scrollable so all columns are visible */}
            <div className="flex-1 max-h-[400px] border rounded-lg overflow-auto">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm">
                  <tr className="border-b">
                    <th className="px-2 py-2 text-left font-medium text-muted-foreground w-10 whitespace-nowrap">#</th>
                    {parseResult.columns.map((col) => (
                      <th key={col} className="px-2 py-2 text-left font-medium text-muted-foreground whitespace-nowrap capitalize">
                        {col.replace(/_/g, ' ')}
                      </th>
                    ))}
                    <th className="px-2 py-2 text-center font-medium text-muted-foreground w-10 whitespace-nowrap">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Valid records */}
                  {parseResult.records.map((record) => (
                    <tr key={record.row} className="border-b hover:bg-muted/50">
                      <td className="px-2 py-1.5 text-muted-foreground text-center">{record.row}</td>
                      {parseResult.columns.map((col) => (
                        <td key={col} className="px-2 py-1.5 max-w-[200px] truncate">
                          {String(record.data[col] ?? '')}
                        </td>
                      ))}
                      <td className="px-2 py-1.5 text-center">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 inline-block" />
                      </td>
                    </tr>
                  ))}

                  {/* Error rows */}
                  {parseResult.errors.map((err, i) => (
                    <tr key={`err-${i}`} className="border-b opacity-60">
                      <td className="px-2 py-1.5 text-muted-foreground text-center">{err.row}</td>
                      <td className="px-2 py-1.5 text-destructive" colSpan={parseResult.columns.length}>
                        {err.message}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        <AlertCircle className="h-3.5 w-3.5 text-destructive inline-block" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

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
