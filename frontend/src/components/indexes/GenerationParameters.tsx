/**
 * LLM generation parameter controls for Answer mode.
 * Shown below retrieval parameters when playground is in Answer mode.
 */
import { Sparkles, Info } from 'lucide-react'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { LLM_MODEL_OPTIONS } from '@/hooks/usePlayground'

interface GenerationParametersProps {
  provider: string
  model: string
  temperature: number
  maxTokens: number
  instructions: string
  onProviderChange: (provider: string) => void
  onModelChange: (model: string) => void
  onTemperatureChange: (t: number) => void
  onMaxTokensChange: (t: number) => void
  onInstructionsChange: (text: string) => void
}

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

export function GenerationParameters({
  provider,
  model,
  temperature,
  maxTokens,
  instructions,
  onProviderChange,
  onModelChange,
  onTemperatureChange,
  onMaxTokensChange,
  onInstructionsChange,
}: GenerationParametersProps) {
  const modelOptions = LLM_MODEL_OPTIONS[provider] ?? []

  return (
    <div className="rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center gap-1.5 mb-4">
        <Sparkles className="h-4 w-4 text-zinc-400" />
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          Generation
        </h3>
      </div>

      {/* Provider */}
      <div className="mb-3">
        <span className="text-xs text-zinc-600 font-medium mb-1.5 block">Provider</span>
        <Select value={provider} onValueChange={onProviderChange}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="openai">OpenAI</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Model */}
      <div className="mb-3">
        <span className="text-xs text-zinc-600 font-medium mb-1.5 block">Model</span>
        <Select value={model} onValueChange={onModelChange}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {modelOptions.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Temperature */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <span className="text-xs text-zinc-600 font-medium">Temperature</span>
            <ParamTooltip text="Higher values produce more creative responses. Lower values are more deterministic." />
          </div>
          <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">
            {temperature.toFixed(1)}
          </span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.1}
          value={[temperature]}
          onValueChange={([v]) => onTemperatureChange(v)}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-400 mt-1">
          <span>0.0 precise</span>
          <span>1.0 creative</span>
        </div>
      </div>

      {/* Max Tokens */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <span className="text-xs text-zinc-600 font-medium">Max Tokens</span>
            <ParamTooltip text="Maximum number of tokens in the generated answer." />
          </div>
          <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">
            {maxTokens}
          </span>
        </div>
        <Slider
          min={256}
          max={4096}
          step={128}
          value={[maxTokens]}
          onValueChange={([v]) => onMaxTokensChange(v)}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-400 mt-1">
          <span>256</span>
          <span>4096</span>
        </div>
      </div>

      {/* Instructions */}
      <div>
        <div className="flex items-center gap-1 mb-1.5">
          <span className="text-xs text-zinc-600 font-medium">Instructions</span>
          <ParamTooltip text="Optional instructions that shape the answer style and content." />
        </div>
        <Textarea
          value={instructions}
          onChange={(e) => onInstructionsChange(e.target.value)}
          placeholder="e.g., Answer as a financial analyst. Be concise."
          rows={3}
          className="text-xs resize-y min-h-[64px] bg-zinc-50 border-zinc-200 focus-visible:ring-zinc-900"
        />
      </div>
    </div>
  )
}
