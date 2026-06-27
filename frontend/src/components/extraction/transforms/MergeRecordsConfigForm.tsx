import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export interface MergeRecordsConfig {
  groupBy: string[]
  keyNormalize?: {
    firstTokenOnly?: boolean
    stripTrailingLetters?: string[]
  }
  spine: {
    whereFieldsPresent: string[]
  }
  conflict: 'prefer_spine' | 'first_non_null'
  onGroupWithoutSpine: 'keep' | 'drop'
}

interface Props {
  value: MergeRecordsConfig
  onChange: (v: MergeRecordsConfig) => void
}

export function MergeRecordsConfigForm({ value, onChange }: Props) {
  const handleGroupBy = (raw: string) => {
    const fields = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onChange({ ...value, groupBy: fields })
  }

  const handleSpineFields = (raw: string) => {
    const fields = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onChange({ ...value, spine: { whereFieldsPresent: fields } })
  }

  const handleFirstTokenOnly = (checked: boolean) => {
    onChange({
      ...value,
      keyNormalize: {
        ...value.keyNormalize,
        firstTokenOnly: checked,
      },
    })
  }

  const handleStripTrailingLetters = (raw: string) => {
    const letters = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onChange({
      ...value,
      keyNormalize: {
        ...value.keyNormalize,
        stripTrailingLetters: letters,
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="groupBy">Group-by fields</Label>
        <Input
          id="groupBy"
          placeholder="e.g. baseModel"
          value={value.groupBy.join(', ')}
          onChange={(e) => handleGroupBy(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">Comma-separated field names to group rows by.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="spineFields">Spine identity fields</Label>
        <Input
          id="spineFields"
          placeholder="e.g. sku"
          value={value.spine.whereFieldsPresent.join(', ')}
          onChange={(e) => handleSpineFields(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">Rows are "spine" rows when these fields are non-null.</p>
      </div>

      <div className="space-y-3">
        <Label>Key normalization</Label>
        <div className="flex items-center gap-2">
          <Checkbox
            id="firstTokenOnly"
            checked={value.keyNormalize?.firstTokenOnly ?? false}
            onCheckedChange={(checked) => handleFirstTokenOnly(checked === true)}
          />
          <Label htmlFor="firstTokenOnly" className="font-normal cursor-pointer">
            First token only
          </Label>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="stripTrailingLetters">Strip trailing letters (comma-separated)</Label>
          <Input
            id="stripTrailingLetters"
            placeholder="e.g. B, X"
            value={(value.keyNormalize?.stripTrailingLetters ?? []).join(', ')}
            onChange={(e) => handleStripTrailingLetters(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Letters stripped from the end of each key token before grouping.
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="conflict">Conflict policy</Label>
        <Select
          value={value.conflict}
          onValueChange={(v) =>
            onChange({ ...value, conflict: v as MergeRecordsConfig['conflict'] })
          }
        >
          <SelectTrigger id="conflict">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="prefer_spine">Prefer spine</SelectItem>
            <SelectItem value="first_non_null">First non-null</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="onGroupWithoutSpine">Groups without a spine row</Label>
        <Select
          value={value.onGroupWithoutSpine}
          onValueChange={(v) =>
            onChange({ ...value, onGroupWithoutSpine: v as MergeRecordsConfig['onGroupWithoutSpine'] })
          }
        >
          <SelectTrigger id="onGroupWithoutSpine">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="keep">Keep</SelectItem>
            <SelectItem value="drop">Drop</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
