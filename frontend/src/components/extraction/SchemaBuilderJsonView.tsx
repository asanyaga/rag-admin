import { Textarea } from '@/components/ui/textarea'

interface SchemaBuilderJsonViewProps {
  value: string
  onChange: (v: string) => void
  parseError: string | null
}

export function SchemaBuilderJsonView({ value, onChange, parseError }: SchemaBuilderJsonViewProps) {
  return (
    <div className="space-y-1">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono text-sm min-h-[300px]"
        placeholder='{"type": "object", "properties": {...}}'
        spellCheck={false}
      />
      {parseError && (
        <p className="text-xs text-destructive">{parseError}</p>
      )}
    </div>
  )
}
