import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export interface MergeRecordsConfig {
  groupBy: string[]
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

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="groupBy">Group-by fields</Label>
        <Input
          id="groupBy"
          placeholder="e.g. productFamily"
          value={value.groupBy.join(', ')}
          onChange={(e) => handleGroupBy(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">Comma-separated field names to group rows by. Values must be pre-normalized.</p>
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
