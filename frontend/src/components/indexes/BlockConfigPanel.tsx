import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Toggle } from '@/components/ui/toggle'
import { BLOCK_ROLE_OPTIONS, BlockRole, IndexConfig } from '@/types/index'

interface BlockConfigPanelProps {
  config: Partial<IndexConfig>
  onUpdate: (key: keyof IndexConfig, value: IndexConfig[keyof IndexConfig]) => void
}

export function BlockConfigPanel({ config, onUpdate }: BlockConfigPanelProps) {
  const groupByHeading = config.groupByHeading ?? true
  const maxBlocks = config.maxBlocksPerChunk ?? 10
  const filter: BlockRole[] = (config.blockRoleFilter as BlockRole[] | null | undefined) ?? []

  const toggleRole = (role: BlockRole) => {
    const next = filter.includes(role)
      ? filter.filter((r) => r !== role)
      : [...filter, role]
    onUpdate('blockRoleFilter', next.length === 0 ? null : next)
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="group-by-heading">Group by heading</Label>
          <Switch
            id="group-by-heading"
            checked={groupByHeading}
            onCheckedChange={(v) => onUpdate('groupByHeading', v)}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Attach paragraphs and tables to their preceding heading.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Max blocks per chunk</Label>
          <span className="text-sm text-muted-foreground">{maxBlocks}</span>
        </div>
        <Slider
          min={1} max={50} step={1}
          value={[maxBlocks]}
          onValueChange={([v]) => onUpdate('maxBlocksPerChunk', v)}
        />
        <p className="text-xs text-muted-foreground">
          Large sections are split and the heading is repeated for context.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Block role filter</Label>
        <p className="text-xs text-muted-foreground">
          {filter.length === 0
            ? 'All block types (default).'
            : `Indexing only: ${filter.join(', ')}.`}
        </p>
        <div className="flex flex-wrap gap-2">
          {BLOCK_ROLE_OPTIONS.map((role) => {
            const active = filter.includes(role)
            return (
              <Toggle
                key={role}
                pressed={active}
                aria-pressed={active}
                onPressedChange={() => toggleRole(role)}
                size="sm"
              >
                {role}
              </Toggle>
            )
          })}
        </div>
      </div>
    </div>
  )
}
