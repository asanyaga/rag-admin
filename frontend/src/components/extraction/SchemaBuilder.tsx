import { useState, useRef, useCallback, useEffect } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Plus, AlertCircle } from 'lucide-react'
import { SchemaBuilderJsonView } from './SchemaBuilderJsonView'
import { SchemaFieldEditor } from './SchemaFieldEditor'
import {
  type SchemaField,
  schemaToFields,
  fieldsToSchema,
  newBlankField,
  getDuplicateKeys,
  hasUnknownKeywords,
  validateFields,
} from '@/lib/schemaBuilder'

const DEBOUNCE_MS = 300

interface SchemaBuilderProps {
  value: Record<string, unknown>
  onChange: (v: Record<string, unknown>) => void
  onValidChange?: (valid: boolean) => void
}

export function SchemaBuilder({ value, onChange, onValidChange }: SchemaBuilderProps) {
  const [fields, setFields] = useState<SchemaField[]>(() => schemaToFields(value))
  const [jsonText, setJsonText] = useState(() => JSON.stringify(value, null, 2))
  const [parseError, setParseError] = useState<string | null>(null)
  const [unknownKeywords, setUnknownKeywords] = useState(() => hasUnknownKeywords(value))
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  const applyFields = useCallback(
    (next: SchemaField[]) => {
      setFields(next)
      const schema = fieldsToSchema(next)
      setJsonText(JSON.stringify(schema, null, 2))
      setUnknownKeywords(false)
      onChange(schema)
      onValidChange?.(validateFields(next) === null)
    },
    [onChange, onValidChange]
  )

  const handleJsonChange = (text: string) => {
    setJsonText(text)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      try {
        const parsed = JSON.parse(text) as Record<string, unknown>
        const next = schemaToFields(parsed)
        setFields(next)
        setUnknownKeywords(hasUnknownKeywords(parsed))
        setParseError(null)
        onChange(parsed)
        onValidChange?.(validateFields(next) === null)
      } catch {
        setParseError('Invalid JSON')
        onValidChange?.(false)
      }
    }, DEBOUNCE_MS)
  }

  const addField = () => applyFields([...fields, newBlankField()])
  const updateField = (i: number, updated: SchemaField) => {
    const next = [...fields]
    next[i] = updated
    applyFields(next)
  }
  const deleteField = (i: number) => applyFields(fields.filter((_, idx) => idx !== i))

  const duplicateKeys = getDuplicateKeys(fields)

  return (
    <Tabs defaultValue="builder">
      <TabsList className="h-8">
        <TabsTrigger value="builder" className="text-xs px-3 h-7">Builder</TabsTrigger>
        <TabsTrigger value="json" className="text-xs px-3 h-7">JSON</TabsTrigger>
      </TabsList>

      <TabsContent value="builder" className="mt-3 space-y-2">
        {unknownKeywords && (
          <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            Some schema keywords aren't editable in Builder view. They're preserved in JSON.
          </div>
        )}
        {fields.map((field, i) => (
          <SchemaFieldEditor
            key={i}
            field={field}
            onChange={(updated) => updateField(i, updated)}
            onDelete={() => deleteField(i)}
            duplicateKeys={duplicateKeys}
          />
        ))}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          onClick={addField}
          type="button"
        >
          <Plus className="h-3 w-3 mr-1" />
          Add field
        </Button>
      </TabsContent>

      <TabsContent value="json" className="mt-3">
        <SchemaBuilderJsonView
          value={jsonText}
          onChange={handleJsonChange}
          parseError={parseError}
        />
      </TabsContent>
    </Tabs>
  )
}
