import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import {
  FileSearch,
  UserCheck,
  Upload,
  Database,
  Zap,
  X,
  type LucideIcon,
} from 'lucide-react'

const categoryIcons: Record<string, LucideIcon> = {
  extraction: FileSearch,
  control: UserCheck,
  export: Upload,
  indexing: Database,
  trigger: Zap,
}

const categoryStyles: Record<string, { bg: string; border: string; accent: string }> = {
  extraction: { bg: 'bg-blue-50', border: 'border-blue-300', accent: 'text-blue-600' },
  control: { bg: 'bg-amber-50', border: 'border-amber-300', accent: 'text-amber-600' },
  export: { bg: 'bg-emerald-50', border: 'border-emerald-300', accent: 'text-emerald-600' },
  indexing: { bg: 'bg-purple-50', border: 'border-purple-300', accent: 'text-purple-600' },
  trigger: { bg: 'bg-orange-50', border: 'border-orange-300', accent: 'text-orange-600' },
}

const defaultStyle = { bg: 'bg-gray-50', border: 'border-gray-300', accent: 'text-gray-600' }

interface ComposerNodeData {
  label: string
  toolSlug: string
  category: string
  config: Record<string, unknown>
  onRemove?: (nodeId: string) => void
  onSelect?: (nodeId: string) => void
}

function ComposerNodeComponent({
  id,
  data,
  selected,
}: {
  id: string
  data: ComposerNodeData
  selected?: boolean
}) {
  const style = categoryStyles[data.category] ?? defaultStyle
  const Icon = categoryIcons[data.category] ?? Zap

  return (
    <>
      <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-slate-400 !border-white !border-2" />
      <div
        className={`relative rounded-lg border-2 px-4 py-3 min-w-[160px] shadow-sm transition-shadow ${
          style.bg
        } ${selected ? 'border-indigo-500 shadow-md ring-2 ring-indigo-200' : style.border}`}
        onClick={() => data.onSelect?.(id)}
      >
        {data.onRemove && (
          <button
            className="absolute -top-2 -right-2 rounded-full bg-white border border-gray-200 p-0.5 shadow-sm hover:bg-red-50 hover:border-red-300 transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              data.onRemove!(id)
            }}
          >
            <X className="h-3 w-3 text-gray-400 hover:text-red-500" />
          </button>
        )}
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${style.accent}`} />
          <span className="text-sm font-medium text-gray-800">
            {data.label}
          </span>
        </div>
        <div className={`text-[10px] mt-1 ${style.accent} opacity-75`}>
          {data.toolSlug}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!w-2.5 !h-2.5 !bg-slate-400 !border-white !border-2" />
    </>
  )
}

export const ComposerNode = memo(ComposerNodeComponent)
