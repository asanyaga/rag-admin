import { useState, useEffect } from 'react'
import type { ExtractionGroundTruthItem } from '@/types/extractionGroundTruth'
import type { ExtractionSchema } from '@/types/extraction'
import { DynamicFieldForm } from './DynamicFieldForm'
import { CsvImportModal } from './CsvImportModal'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { ArrowLeft, ChevronLeft, ChevronRight, Save, Code, FormInput, Upload } from 'lucide-react'
import { toast } from 'sonner'

interface GroundTruthEditorProps {
  item: ExtractionGroundTruthItem
  items: ExtractionGroundTruthItem[]
  schema: ExtractionSchema | null
  onSave: (itemId: string, expectedData: Record<string, unknown>, annotations: Record<string, unknown> | null) => Promise<void>
  onBack: () => void
  onNavigate: (item: ExtractionGroundTruthItem) => void
}

export function GroundTruthEditor({
  item,
  items,
  schema,
  onSave,
  onBack,
  onNavigate,
}: GroundTruthEditorProps) {
  const [expectedData, setExpectedData] = useState<Record<string, unknown>>(item.expectedData)
  const [annotations, setAnnotations] = useState<Record<string, unknown>>(item.annotations || {})
  const [jsonMode, setJsonMode] = useState(false)
  const [jsonText, setJsonText] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [csvImportOpen, setCsvImportOpen] = useState(false)

  const currentIndex = items.findIndex((i) => i.id === item.id)
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < items.length - 1

  useEffect(() => {
    setExpectedData(item.expectedData)
    setAnnotations(item.annotations || {})
    setJsonText(JSON.stringify(item.expectedData, null, 2))
  }, [item])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      let data = expectedData
      if (jsonMode) {
        try {
          data = JSON.parse(jsonText)
        } catch {
          toast.error('Invalid JSON')
          setIsSaving(false)
          return
        }
      }
      await onSave(item.id, data, Object.keys(annotations).length > 0 ? annotations : null)
      toast.success('Saved')
    } catch (err) {
      toast.error('Failed to save', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const toggleMode = () => {
    if (!jsonMode) {
      setJsonText(JSON.stringify(expectedData, null, 2))
    } else {
      try {
        setExpectedData(JSON.parse(jsonText))
      } catch {
        toast.error('Invalid JSON — switching back to form mode')
        return
      }
    }
    setJsonMode(!jsonMode)
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <p className="text-sm font-medium truncate max-w-[200px]">
              {item.documentTitle || 'Untitled'}
            </p>
            <p className="text-xs text-muted-foreground">
              {currentIndex + 1} of {items.length}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            disabled={!hasPrev}
            onClick={() => hasPrev && onNavigate(items[currentIndex - 1])}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            disabled={!hasNext}
            onClick={() => hasNext && onNavigate(items[currentIndex + 1])}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={toggleMode}
            className="ml-2"
          >
            {jsonMode ? <FormInput className="h-3.5 w-3.5 mr-1.5" /> : <Code className="h-3.5 w-3.5 mr-1.5" />}
            {jsonMode ? 'Form' : 'JSON'}
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving} className="ml-1">
            <Save className="h-3.5 w-3.5 mr-1.5" />
            Save
          </Button>
        </div>
      </div>

      {/* Editor content */}
      <div className="space-y-6 max-w-lg">
        {/* Schema name */}
        {schema && (
          <p className="text-xs text-muted-foreground">
            Schema: {schema.name}
          </p>
        )}

        {/* Expected data */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">Expected Output</h3>
            {schema && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCsvImportOpen(true)}
              >
                <Upload className="h-3.5 w-3.5 mr-1.5" />
                Import CSV
              </Button>
            )}
          </div>
          {jsonMode ? (
            <Textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              className="font-mono text-sm min-h-[300px]"
              spellCheck={false}
            />
          ) : schema ? (
            <DynamicFieldForm
              schemaDefinition={schema.schemaDefinition}
              data={expectedData}
              onChange={setExpectedData}
            />
          ) : (
            <Textarea
              value={JSON.stringify(expectedData, null, 2)}
              onChange={(e) => {
                try {
                  setExpectedData(JSON.parse(e.target.value))
                } catch {
                  // ignore parse errors during typing
                }
              }}
              className="font-mono text-sm min-h-[200px]"
            />
          )}
        </div>

        <Separator />

        {/* Annotations */}
        <div>
          <h3 className="text-sm font-medium mb-3">Annotations</h3>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Quality</Label>
              <Select
                value={String(annotations.quality || '')}
                onValueChange={(v) => setAnnotations({ ...annotations, quality: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select quality" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="clean">Clean</SelectItem>
                  <SelectItem value="faded">Faded</SelectItem>
                  <SelectItem value="crumpled">Crumpled</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Difficulty</Label>
              <Select
                value={String(annotations.difficulty || '')}
                onValueChange={(v) => setAnnotations({ ...annotations, difficulty: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select difficulty" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">Easy</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="hard">Hard</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Notes</Label>
              <Input
                value={String(annotations.notes || '')}
                onChange={(e) => setAnnotations({ ...annotations, notes: e.target.value })}
                placeholder="Any additional notes..."
              />
            </div>
          </div>
        </div>
      </div>

      {/* CSV Import Modal */}
      {schema && (
        <CsvImportModal
          open={csvImportOpen}
          onOpenChange={setCsvImportOpen}
          schemaDefinition={schema.schemaDefinition}
          onImport={(records) => {
            // Modal returns:
            // - Array schema: [{ transactions: [row1, row2, ...] }] — single wrapped record
            // - Scalar schema: [row1, row2, ...] — each row is a flat record
            const data = records[0]
            setExpectedData(data)
            setJsonText(JSON.stringify(data, null, 2))
            toast.success('Expected output imported from CSV')
          }}
        />
      )}
    </div>
  )
}
