/**
 * Retrieval parameter controls: search type, top-k, and threshold
 */
import { SearchType } from '@/types/index'
import { Slider } from '@/components/ui/slider'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { SlidersHorizontal, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

interface RetrievalParametersProps {
  searchType: SearchType
  topK: number
  threshold: number
  onSearchTypeChange: (type: SearchType) => void
  onTopKChange: (k: number) => void
  onThresholdChange: (t: number) => void
}

const SEARCH_TYPES: SearchType[] = ['semantic', 'keyword', 'hybrid']

function ParamTooltip({ text }: { text: string }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Info className="h-3.5 w-3.5 text-zinc-300 cursor-help" />
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function RetrievalParameters({
  searchType,
  topK,
  threshold,
  onSearchTypeChange,
  onTopKChange,
  onThresholdChange,
}: RetrievalParametersProps) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center gap-1.5 mb-4">
        <SlidersHorizontal className="h-4 w-4 text-zinc-400" />
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          Parameters
        </h3>
      </div>

      {/* Search Type Toggle */}
      <div className="mb-4">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-xs text-zinc-600 font-medium">Search Type</span>
          <ParamTooltip text="Semantic finds conceptually similar content. Keyword matches exact words. Hybrid combines both." />
        </div>
        <div className="flex gap-0.5 bg-zinc-100 rounded-md p-0.5">
          {SEARCH_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => onSearchTypeChange(type)}
              className={cn(
                'flex-1 py-1.5 rounded text-xs font-medium capitalize transition-all',
                searchType === type
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-600'
              )}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Top-K Slider */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <span className="text-xs text-zinc-600 font-medium">Top-K</span>
            <ParamTooltip text="Number of chunks to retrieve. More results = broader recall but potentially lower precision." />
          </div>
          <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">
            {topK}
          </span>
        </div>
        <Slider
          min={1}
          max={20}
          step={1}
          value={[topK]}
          onValueChange={([v]) => onTopKChange(v)}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-400 mt-1">
          <span>1</span>
          <span>20</span>
        </div>
      </div>

      {/* Threshold Slider */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <span className="text-xs text-zinc-600 font-medium">Threshold</span>
            <ParamTooltip text="Only show results above this relevance score. Higher = stricter matching, fewer results." />
          </div>
          <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">
            {threshold.toFixed(1)}
          </span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.1}
          value={[threshold]}
          onValueChange={([v]) => onThresholdChange(v)}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-400 mt-1">
          <span>0.0 all</span>
          <span>1.0 strict</span>
        </div>
      </div>
    </div>
  )
}
