import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { ParseRunListItem } from '@/types/cdm'
import { ChevronDown, RefreshCw, Trash2 } from 'lucide-react'

interface RunHeaderProps {
  run: ParseRunListItem
  onReparse: () => void
  onDelete: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function statusVariant(
  status: ParseRunListItem['status']
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'succeeded':
      return 'default'
    case 'failed':
      return 'destructive'
    case 'partial':
      return 'secondary'
    default:
      return 'outline'
  }
}

export function RunHeader({ run, onReparse, onDelete }: RunHeaderProps) {
  const [configOpen, setConfigOpen] = useState(false)
  return (
    <div className="border-b bg-background sticky top-0 z-10">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        <span className="text-sm font-medium">
          {run.parser}
          {run.parserVersion && (
            <span className="text-muted-foreground">@{run.parserVersion}</span>
          )}
        </span>
        <span className="text-xs text-muted-foreground">
          {run.representationKind}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatDuration(run.durationMs)}
        </span>
        {(run.inputTokens !== null || run.outputTokens !== null) && (
          <span className="text-xs text-muted-foreground">
            tokens: {run.inputTokens ?? '—'} / {run.outputTokens ?? '—'}
          </span>
        )}
        {Object.keys(run.cost).length > 0 && (
          <span className="text-xs text-muted-foreground">
            cost: {JSON.stringify(run.cost)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={onReparse}>
            <RefreshCw className="h-3 w-3 mr-1" /> Re-parse
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
            aria-label="Delete run"
          >
            <Trash2 className="h-3 w-3 mr-1" /> Delete
          </Button>
        </div>
      </div>
      {run.error && (
        <div className="px-4 py-2 text-xs text-destructive border-t bg-destructive/5">
          {run.error}
        </div>
      )}
      <Collapsible open={configOpen} onOpenChange={setConfigOpen}>
        <CollapsibleTrigger asChild>
          <button className="w-full text-left px-4 py-1 text-xs text-muted-foreground hover:bg-muted/40 flex items-center gap-1">
            <ChevronDown
              className={`h-3 w-3 transition-transform ${
                configOpen ? '' : '-rotate-90'
              }`}
            />
            Config
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="px-4 pb-3 text-xs font-mono whitespace-pre-wrap text-muted-foreground">
            {JSON.stringify(run.config, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
