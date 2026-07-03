import type { ClassificationFilterState } from '@/hooks/useClassificationFilter'
import { ClassificationConfig } from '@/components/classification/ClassificationConfig'
import type { ClassificationConfigValue } from '@/components/classification/ClassificationConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

interface Props {
  state: ClassificationFilterState
  classifyConfig: ClassificationConfigValue
  onClassifyConfigChange: (v: ClassificationConfigValue) => void
  promptConfig: PromptConfig
  onPromptConfigChange: (v: PromptConfig) => void
}

function CategoryChecklist({
  categories, selected, onToggle,
}: { categories: string[]; selected: string[]; onToggle: (c: string) => void }) {
  return (
    <div className="space-y-2">
      {categories.map((cat) => (
        <div key={cat} className="flex items-center gap-2">
          <Checkbox id={`cat-${cat}`} checked={selected.includes(cat)} onCheckedChange={() => onToggle(cat)} />
          <Label htmlFor={`cat-${cat}`}>{cat}</Label>
        </div>
      ))}
    </div>
  )
}

export function ClassificationFilterSection({
  state, classifyConfig, onClassifyConfigChange, promptConfig, onPromptConfigChange,
}: Props) {
  const { mode, selectCategories, selectedCategories, granularity, setSelectedCategories, setGranularity } = state

  const toggle = (cat: string) =>
    setSelectedCategories(
      selectedCategories.includes(cat)
        ? selectedCategories.filter((c) => c !== cat)
        : [...selectedCategories, cat],
    )

  const granularitySelect = (
    <div className="flex items-center gap-2">
      <Label htmlFor="granularity">Granularity</Label>
      <select id="granularity" className="rounded border px-2 py-1 text-sm"
        value={granularity} onChange={(e) => setGranularity(e.target.value as 'page' | 'block')}>
        <option value="page">Page</option>
        <option value="block">Block</option>
      </select>
    </div>
  )

  if (mode === 'select') {
    return (
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">Filter extraction to these classified categories:</p>
        <CategoryChecklist categories={selectCategories} selected={selectedCategories} onToggle={toggle} />
        {granularitySelect}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        No classification exists for this parse. Configure one — it runs before extraction.
      </p>
      <ClassificationConfig defaultValues={classifyConfig} onChange={onClassifyConfigChange} />
      {classifyConfig.classifierType === 'llm' && (
        <PromptConfigEditor value={promptConfig} onChange={onPromptConfigChange} />
      )}
      {classifyConfig.labels.length > 0 && (
        <div className="space-y-2">
          <Label className="text-xs">Filter extraction to</Label>
          <CategoryChecklist categories={classifyConfig.labels} selected={selectedCategories} onToggle={toggle} />
        </div>
      )}
      {granularitySelect}
    </div>
  )
}
