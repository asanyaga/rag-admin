import type { PageProfile } from '@/types/probeReport'
import { cn } from '@/lib/utils'
import { RegionCard } from './RegionCard'

interface Props {
  page: PageProfile
  selected: boolean
  onSelect: (index: number) => void
}

export function PageCard({ page, selected, onSelect }: Props) {
  return (
    <button
      onClick={() => onSelect(page.index)}
      className={cn(
        'w-full text-left rounded-md border p-3 mb-2 hover:bg-muted/40',
        selected && 'ring-2 ring-primary',
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold">Page {page.index + 1}</span>
        <span className="text-xs text-muted-foreground">{page.page_type}</span>
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {page.signals.map((s) => (
          <span key={s.name} className="text-[10px] px-1.5 rounded-full bg-muted">
            {s.name}: {String(s.value)}
          </span>
        ))}
      </div>
      {page.regions.map((r) => (
        <RegionCard key={r.id} region={r} />
      ))}
    </button>
  )
}
