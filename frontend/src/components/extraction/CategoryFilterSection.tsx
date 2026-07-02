import type { CategoryFilterState } from '@/hooks/useCategoryFilter'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

interface Props {
  state: CategoryFilterState
}

export function CategoryFilterSection({ state }: Props) {
  const {
    eligibleRun, availableCategories, selectedCategories,
    granularity, setSelectedCategories, setGranularity,
  } = state

  if (!eligibleRun) {
    return (
      <p className="text-sm text-muted-foreground">
        No completed classification run exists for this parse. Run classification on
        this document first to filter extraction by category.
      </p>
    )
  }

  const toggle = (cat: string) => {
    setSelectedCategories(
      selectedCategories.includes(cat)
        ? selectedCategories.filter((c) => c !== cat)
        : [...selectedCategories, cat],
    )
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {availableCategories.map((cat) => (
          <div key={cat} className="flex items-center gap-2">
            <Checkbox
              id={`cat-${cat}`}
              checked={selectedCategories.includes(cat)}
              onCheckedChange={() => toggle(cat)}
            />
            <Label htmlFor={`cat-${cat}`}>{cat}</Label>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Label htmlFor="granularity">Granularity</Label>
        <select
          id="granularity"
          className="rounded border px-2 py-1 text-sm"
          value={granularity}
          onChange={(e) => setGranularity(e.target.value as 'page' | 'block')}
        >
          <option value="page">Page</option>
          <option value="block">Block</option>
        </select>
      </div>
    </div>
  )
}
