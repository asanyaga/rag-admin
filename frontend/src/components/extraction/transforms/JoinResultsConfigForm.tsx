import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { X } from 'lucide-react'
import type { JoinResultsConfig } from '@/types/resultTransform'
import type { ExtractionResultListItem } from '@/types/extraction'

const MAX_TOTAL_INPUTS = 5

interface Props {
  value: JoinResultsConfig
  onChange: (v: JoinResultsConfig) => void
  primaryResultId: string
  availableResults: ExtractionResultListItem[]
}

export function JoinResultsConfigForm({ value, onChange, primaryResultId, availableResults }: Props) {
  const patch = (p: Partial<JoinResultsConfig>) => onChange({ ...value, ...p })

  const unselected = availableResults.filter(
    (r) => r.id !== primaryResultId && !value.lookupResultIds.includes(r.id)
  )
  const canAddMore = unselected.length > 0 && value.lookupResultIds.length < MAX_TOTAL_INPUTS - 1

  function addLookup() {
    const next = unselected[0]
    if (!next) return
    patch({ lookupResultIds: [...value.lookupResultIds, next.id] })
  }

  function removeLookup(id: string) {
    patch({ lookupResultIds: value.lookupResultIds.filter((r) => r !== id) })
  }

  function changeLookup(oldId: string, newId: string) {
    patch({
      lookupResultIds: value.lookupResultIds.map((r) => (r === oldId ? newId : r)),
    })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Join key</Label>
        <Input
          value={value.joinKey}
          onChange={(e) => patch({ joinKey: e.target.value })}
          placeholder="e.g. series"
          className="h-8 text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Column name present in all inputs used to match rows.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label>Join type</Label>
        <div className="flex gap-2">
          {(['left', 'inner'] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={value.joinType === t ? 'default' : 'outline'}
              onClick={() => patch({ joinType: t })}
              className="capitalize"
            >
              {t}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {value.joinType === 'left'
            ? 'Keep all left rows; null-key rows always pass through.'
            : 'Only matched rows; null-key rows always pass through.'}
        </p>
      </div>

      <div className="space-y-2">
        <Label>Inputs</Label>

        <div className="flex items-center gap-2 rounded border px-3 py-2 bg-muted/30">
          <span className="text-sm font-mono truncate flex-1">{primaryResultId}</span>
          <Badge variant="secondary" className="text-xs">Primary</Badge>
        </div>

        {value.lookupResultIds.map((rid) => {
          const optionsForThisSlot = availableResults.filter(
            (r) =>
              r.id !== primaryResultId &&
              (r.id === rid || !value.lookupResultIds.includes(r.id))
          )
          return (
            <div key={rid} className="flex items-center gap-2">
              <Select value={rid} onValueChange={(v) => changeLookup(rid, v)}>
                <SelectTrigger className="h-8 text-sm flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {optionsForThisSlot.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0"
                title="Remove lookup"
                onClick={() => removeLookup(rid)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )
        })}

        {canAddMore && (
          <Button size="sm" variant="outline" onClick={addLookup}>
            Add lookup
          </Button>
        )}
      </div>
    </div>
  )
}
