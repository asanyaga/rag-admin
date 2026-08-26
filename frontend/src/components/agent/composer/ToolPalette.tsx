import type { AgentTool } from '@/types/agent'
import { Skeleton } from '@/components/ui/skeleton'
import {
  FileSearch,
  FileText,
  UserCheck,
  Upload,
  Database,
  Zap,
  type LucideIcon,
} from 'lucide-react'

const categoryIcons: Record<string, LucideIcon> = {
  extraction: FileSearch,
  parsing: FileText,
  control: UserCheck,
  export: Upload,
  indexing: Database,
  trigger: Zap,
}

const categoryColors: Record<string, string> = {
  extraction: 'border-blue-300 bg-blue-50 text-blue-700',
  parsing: 'border-cyan-300 bg-cyan-50 text-cyan-700',
  control: 'border-amber-300 bg-amber-50 text-amber-700',
  export: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  indexing: 'border-purple-300 bg-purple-50 text-purple-700',
  trigger: 'border-orange-300 bg-orange-50 text-orange-700',
}

interface ToolPaletteProps {
  tools: AgentTool[]
  isLoading: boolean
}

export function ToolPalette({ tools, isLoading }: ToolPaletteProps) {
  const grouped = tools.reduce<Record<string, AgentTool[]>>((acc, tool) => {
    const cat = tool.category
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(tool)
    return acc
  }, {})

  const onDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    tool: AgentTool
  ) => {
    e.dataTransfer.setData('application/agent-tool', JSON.stringify(tool))
    e.dataTransfer.effectAllowed = 'move'
  }

  if (isLoading) {
    return (
      <div className="space-y-2 p-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-4 p-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Tools
      </div>
      {Object.entries(grouped).map(([category, categoryTools]) => {
        const Icon = categoryIcons[category] ?? Zap
        return (
          <div key={category} className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground capitalize">
              <Icon className="h-3 w-3" />
              {category}
            </div>
            {categoryTools.map((tool) => (
              <div
                key={tool.slug}
                draggable
                onDragStart={(e) => onDragStart(e, tool)}
                className={`cursor-grab rounded-md border px-3 py-2 text-sm font-medium transition-shadow hover:shadow-md active:cursor-grabbing ${
                  categoryColors[category] ?? 'border-gray-300 bg-gray-50 text-gray-700'
                }`}
                title={tool.description}
              >
                {tool.name}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
