/**
 * Session-scoped query history list
 */
import { Clock } from 'lucide-react'

interface QueryHistoryProps {
  history: string[]
  onSelect: (query: string) => void
}

export function QueryHistory({ history, onSelect }: QueryHistoryProps) {
  if (history.length === 0) return null

  return (
    <div className="rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center gap-1.5 mb-3">
        <Clock className="h-3.5 w-3.5 text-zinc-400" />
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          History
        </h3>
      </div>
      <div className="flex flex-col gap-0.5">
        {history.map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect(q)}
            className="text-left px-2 py-1.5 rounded-md text-xs text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700 transition-colors truncate"
            title={q}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
