import { useState, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import {
  Upload,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
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
import * as api from '@/api/golden-sets'
import type {
  ImportParseResponse,
  ImportValidQuery,
  ImportConfirmQuery,
} from '@/types/golden-set'

interface ImportModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  goldenSetId: string
  onImportComplete: () => void
}

type Step = 'upload' | 'preview' | 'result'

const CSV_TEMPLATE = `query_text,document_name,pages
"What is the refund policy?","Returns Policy v2","1,2"
"How long does shipping take?","Shipping Guide","4"
"What payment methods are accepted?",,""`

export function ImportModal({
  open,
  onOpenChange,
  projectId,
  goldenSetId,
  onImportComplete,
}: ImportModalProps) {
  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [parseResult, setParseResult] = useState<ImportParseResponse | null>(null)
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [importedCount, setImportedCount] = useState(0)
  const [parseError, setParseError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = useCallback(() => {
    setStep('upload')
    setFile(null)
    setParsing(false)
    setImporting(false)
    setParseResult(null)
    setSelectedRows(new Set())
    setImportedCount(0)
    setParseError(null)
  }, [])

  const handleOpenChange = (open: boolean) => {
    if (!open) reset()
    onOpenChange(open)
  }

  const handleFileSelect = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase()
    if (ext !== 'csv' && ext !== 'json') {
      toast.error('Please select a .csv or .json file')
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
      const result = await api.parseImport(projectId, goldenSetId, file)
      setParseResult(result)
      // Select all valid rows by default
      setSelectedRows(new Set(result.validQueries.map((_, i) => i)))
      setStep('preview')
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to parse file'
      setParseError(message)
    } finally {
      setParsing(false)
    }
  }

  const handleImport = async () => {
    if (!parseResult) return
    setImporting(true)
    try {
      const queries: ImportConfirmQuery[] = parseResult.validQueries
        .filter((_, i) => selectedRows.has(i))
        .map((q) => ({
          queryText: q.queryText,
          sources: q.sources
            .filter((s) => s.resolved && s.documentId)
            .map((s) => ({
              documentId: s.documentId!,
              locator: s.pages.length > 0 ? { type: 'page', pages: s.pages } : {},
            })),
        }))

      const result = await api.confirmImport(projectId, goldenSetId, {
        queries,
      })
      setImportedCount(result.importedCount)
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
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const toggleAll = () => {
    if (!parseResult) return
    if (selectedRows.size === parseResult.validQueries.length) {
      setSelectedRows(new Set())
    } else {
      setSelectedRows(new Set(parseResult.validQueries.map((_, i) => i)))
    }
  }

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'golden_set_import_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const selectedCount = selectedRows.size

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Import Questions</DialogTitle>
          <DialogDescription>
            {step === 'upload' && 'Upload a CSV or JSON file to import questions.'}
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
                accept=".csv,.json"
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
                      Drop a file here or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Supports .csv and .json
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
              <Button
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
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
                {parseResult.summary.validCount} valid
              </Badge>
              {parseResult.summary.errorCount > 0 && (
                <Badge variant="destructive">
                  {parseResult.summary.errorCount} errors
                </Badge>
              )}
              {parseResult.summary.duplicateCount > 0 && (
                <Badge variant="warning">
                  {parseResult.summary.duplicateCount} duplicates
                </Badge>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {parseResult.summary.totalRows} total rows parsed
              </span>
            </div>

            {/* Table */}
            <ScrollArea className="flex-1 max-h-[400px] border rounded-lg">
              <div className="min-w-0">
                {/* Header */}
                <div className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm border-b px-3 py-2 flex items-center gap-3 text-xs font-medium text-muted-foreground">
                  <Checkbox
                    checked={
                      parseResult.validQueries.length > 0 &&
                      selectedRows.size === parseResult.validQueries.length
                    }
                    onCheckedChange={toggleAll}
                    aria-label="Select all"
                  />
                  <span className="w-8 text-center">#</span>
                  <span className="flex-1">Query</span>
                  <span className="w-40">Sources</span>
                  <span className="w-14 text-center">Status</span>
                </div>

                {/* Valid rows */}
                {parseResult.validQueries.map((q, i) => (
                  <QueryPreviewRow
                    key={i}
                    query={q}
                    selected={selectedRows.has(i)}
                    onToggle={() => toggleRow(i)}
                  />
                ))}

                {/* Duplicate rows */}
                {parseResult.duplicates.map((d, i) => (
                  <div
                    key={`dup-${i}`}
                    className="flex items-center gap-3 px-3 py-2 border-b text-sm opacity-60"
                  >
                    <Checkbox disabled checked={false} />
                    <span className="w-8 text-center text-xs text-muted-foreground">
                      {d.row}
                    </span>
                    <span className="flex-1 truncate">{d.queryText}</span>
                    <span className="w-40 text-xs text-muted-foreground">-</span>
                    <span className="w-14 flex justify-center">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>
                            <Copy className="h-3.5 w-3.5 text-amber-500" />
                          </TooltipTrigger>
                          <TooltipContent>Duplicate — already exists</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </span>
                  </div>
                ))}

                {/* Error rows */}
                {parseResult.errors.map((e, i) => (
                  <div
                    key={`err-${i}`}
                    className="flex items-center gap-3 px-3 py-2 border-b text-sm opacity-60"
                  >
                    <Checkbox disabled checked={false} />
                    <span className="w-8 text-center text-xs text-muted-foreground">
                      {e.row}
                    </span>
                    <span className="flex-1 truncate">
                      {e.queryText || <em className="text-muted-foreground">Empty</em>}
                    </span>
                    <span className="w-40 text-xs text-destructive truncate">
                      {e.error}
                    </span>
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
                Import {selectedCount} {selectedCount === 1 ? 'query' : 'queries'}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Result */}
        {step === 'result' && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-3 py-6">
              <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              <p className="text-lg font-medium">
                Imported {importedCount} {importedCount === 1 ? 'query' : 'queries'}
              </p>
              <p className="text-sm text-muted-foreground">
                Imported queries are set to &ldquo;pending&rdquo; review status.
              </p>
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

function QueryPreviewRow({
  query,
  selected,
  onToggle,
}: {
  query: ImportValidQuery
  selected: boolean
  onToggle: () => void
}) {
  const sourceText =
    query.sources.length === 0
      ? 'No sources'
      : query.sources
          .map((s) => {
            const pages = s.pages.length > 0 ? ` (p${s.pages.join(',')})` : ''
            return `${s.documentName}${pages}`
          })
          .join('; ')

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 border-b text-sm hover:bg-muted/50 transition-colors ${
        selected ? '' : 'opacity-50'
      }`}
    >
      <Checkbox checked={selected} onCheckedChange={onToggle} />
      <span className="w-8 text-center text-xs text-muted-foreground">
        {query.row}
      </span>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex-1 truncate cursor-default">{query.queryText}</span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-sm">
            {query.queryText}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="w-40 text-xs text-muted-foreground truncate cursor-default">
              {sourceText}
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-sm">
            {sourceText}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <span className="w-14 flex justify-center">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
      </span>
    </div>
  )
}
