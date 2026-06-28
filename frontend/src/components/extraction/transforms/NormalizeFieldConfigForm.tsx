import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Trash2, Plus } from 'lucide-react'
import type { NormalizeFieldConfig, NormalizeFieldEntry, NormalizeFieldRule } from '@/types/resultTransform'

const RULE_TYPES = [
  'trim', 'collapseWhitespace', 'lowercase', 'uppercase', 'titlecase',
  'stripRegex', 'stripTrailingChars', 'stripPrefix', 'stripSuffix',
  'split', 'regexExtract', 'replace', 'alias', 'nullifyIfIn',
]

interface RuleRowProps {
  rule: NormalizeFieldRule
  onChange: (r: NormalizeFieldRule) => void
  onRemove: () => void
}

function RuleRow({ rule, onChange, onRemove }: RuleRowProps) {
  const patch = (p: Partial<NormalizeFieldRule>) => onChange({ ...rule, ...p })
  return (
    <div className="border rounded p-3 space-y-2 bg-muted/30">
      <div className="flex items-center gap-2">
        <Select value={rule.type} onValueChange={(v) => onChange({ type: v })}>
          <SelectTrigger className="h-8 text-sm flex-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RULE_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={onRemove} title="Remove rule">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      {rule.type === 'trim' && (
        <Input
          placeholder="chars to strip (optional, default: whitespace)"
          value={typeof rule.chars === 'string' ? rule.chars : ''}
          onChange={(e) => patch({ chars: e.target.value || undefined })}
        />
      )}
      {(rule.type === 'stripRegex' || rule.type === 'regexExtract') && (
        <Input
          placeholder="regex pattern"
          value={rule.pattern ?? ''}
          onChange={(e) => patch({ pattern: e.target.value })}
        />
      )}
      {rule.type === 'regexExtract' && (
        <Input
          placeholder="capture group (name or index, default 0)"
          value={rule.group != null ? String(rule.group) : ''}
          onChange={(e) => patch({ group: e.target.value || undefined })}
        />
      )}
      {rule.type === 'stripTrailingChars' && (
        <Input
          placeholder="chars to strip, comma-separated (e.g. B,D,S,C)"
          value={Array.isArray(rule.chars) ? rule.chars.join(',') : ''}
          onChange={(e) =>
            patch({ chars: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
          }
        />
      )}
      {rule.type === 'stripPrefix' && (
        <Input
          placeholder="prefix to remove"
          value={rule.prefix ?? ''}
          onChange={(e) => patch({ prefix: e.target.value })}
        />
      )}
      {rule.type === 'stripSuffix' && (
        <Input
          placeholder="suffix to remove"
          value={rule.suffix ?? ''}
          onChange={(e) => patch({ suffix: e.target.value })}
        />
      )}
      {rule.type === 'split' && (
        <div className="flex gap-2">
          <Input
            placeholder="delimiter"
            value={rule.delimiter ?? ''}
            onChange={(e) => patch({ delimiter: e.target.value })}
            className="flex-1"
          />
          <Input
            placeholder="index"
            type="number"
            value={rule.index != null ? String(rule.index) : ''}
            onChange={(e) => patch({ index: parseInt(e.target.value, 10) })}
            className="w-20"
          />
        </div>
      )}
      {rule.type === 'replace' && (
        <div className="flex gap-2">
          <Input
            placeholder="find (literal)"
            value={rule.find ?? ''}
            onChange={(e) => patch({ find: e.target.value })}
            className="flex-1"
          />
          <Input
            placeholder="replacement"
            value={rule.replacement ?? ''}
            onChange={(e) => patch({ replacement: e.target.value })}
            className="flex-1"
          />
        </div>
      )}
      {rule.type === 'alias' && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">One mapping per line: <code>from → to</code></p>
          <textarea
            className="w-full text-sm font-mono border rounded p-2 min-h-[4rem] bg-background"
            placeholder={'UX-50L → UX-50 LITE\nGP-40 LITE → GP-40L'}
            value={Object.entries(rule.map ?? {}).map(([k, v]) => `${k} → ${v}`).join('\n')}
            onChange={(e) => {
              const map: Record<string, string> = {}
              for (const line of e.target.value.split('\n')) {
                const [k, ...rest] = line.split('→')
                if (k && rest.length) map[k.trim()] = rest.join('→').trim()
              }
              patch({ map })
            }}
          />
        </div>
      )}
      {rule.type === 'nullifyIfIn' && (
        <Input
          placeholder="values to nullify, comma-separated (e.g. N/A,-,0)"
          value={Array.isArray(rule.values) ? rule.values.join(',') : ''}
          onChange={(e) =>
            patch({ values: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
          }
        />
      )}
    </div>
  )
}

const EMPTY_ENTRY: NormalizeFieldEntry = { sourceField: '', outputField: '', rules: [] }

interface FieldEntryProps {
  entry: NormalizeFieldEntry
  index: number
  canRemove: boolean
  onChange: (e: NormalizeFieldEntry) => void
  onRemove: () => void
}

function FieldEntry({ entry, index, canRemove, onChange, onRemove }: FieldEntryProps) {
  const updateRule = (i: number, rule: NormalizeFieldRule) => {
    const rules = [...entry.rules]
    rules[i] = rule
    onChange({ ...entry, rules })
  }
  const removeRule = (i: number) => {
    onChange({ ...entry, rules: entry.rules.filter((_, idx) => idx !== i) })
  }
  const addRule = () => {
    onChange({ ...entry, rules: [...entry.rules, { type: 'trim' }] })
  }

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Field {index + 1}
        </span>
        {canRemove && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onRemove} title="Remove field">
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Source field</Label>
          <Input
            placeholder="e.g. modelName"
            value={entry.sourceField}
            onChange={(e) => onChange({ ...entry, sourceField: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Output field</Label>
          <Input
            placeholder="e.g. baseModel"
            value={entry.outputField}
            onChange={(e) => onChange({ ...entry, outputField: e.target.value })}
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Rules</Label>
          <Button variant="outline" size="sm" className="h-6 text-xs gap-1" onClick={addRule}>
            <Plus className="h-3 w-3" />
            Add rule
          </Button>
        </div>
        {entry.rules.length === 0 && (
          <p className="text-xs text-muted-foreground italic">No rules yet.</p>
        )}
        {entry.rules.map((rule, i) => (
          <RuleRow key={i} rule={rule} onChange={(r) => updateRule(i, r)} onRemove={() => removeRule(i)} />
        ))}
      </div>
    </div>
  )
}

interface Props {
  value: NormalizeFieldConfig
  onChange: (v: NormalizeFieldConfig) => void
}

export function NormalizeFieldConfigForm({ value, onChange }: Props) {
  const updateEntry = (i: number, entry: NormalizeFieldEntry) => {
    const fields = [...value.fields]
    fields[i] = entry
    onChange({ fields })
  }
  const removeEntry = (i: number) => {
    onChange({ fields: value.fields.filter((_, idx) => idx !== i) })
  }
  const addEntry = () => {
    onChange({ fields: [...value.fields, { ...EMPTY_ENTRY }] })
  }

  return (
    <div className="space-y-3">
      {value.fields.map((entry, i) => (
        <FieldEntry
          key={i}
          entry={entry}
          index={i}
          canRemove={value.fields.length > 1}
          onChange={(e) => updateEntry(i, e)}
          onRemove={() => removeEntry(i)}
        />
      ))}
      <Button variant="outline" size="sm" className="w-full h-8 text-xs gap-1.5" onClick={addEntry}>
        <Plus className="h-3.5 w-3.5" />
        Add field
      </Button>
    </div>
  )
}
