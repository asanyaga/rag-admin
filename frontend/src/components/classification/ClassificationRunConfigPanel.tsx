import { useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import type { ClassificationRun } from '@/types/classification'

interface Props {
  run: ClassificationRun
}

export function ClassificationRunConfigPanel({ run }: Props) {
  const [promptExpanded, setPromptExpanded] = useState(false)

  const cfg = run.classifierConfig as Record<string, unknown>
  const llmCfg = (cfg.llm_config as Record<string, unknown> | undefined) ?? {}
  const isLlm = run.classifierType === 'llm'

  return (
    <div className="space-y-3 text-sm">
      {/* Classification run */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Classification run
        </p>
        <div className="space-y-1 text-xs">
          <div className="flex gap-2">
            <span className="text-muted-foreground w-24 shrink-0">Classifier</span>
            <span>{run.classifierType}</span>
          </div>
          <div className="flex gap-2 items-start">
            <span className="text-muted-foreground w-24 shrink-0 mt-0.5">Labels</span>
            <div className="flex flex-wrap gap-1">
              {run.labelsRequested.map((l) => (
                <Badge key={l} variant="secondary" className="text-xs font-normal">
                  {l}
                </Badge>
              ))}
            </div>
          </div>
          {isLlm && (
            <>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Batch size</span>
                <span>{String(cfg.batch_size ?? '—')} pages</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Batch overlap</span>
                <span>{String(cfg.batch_overlap ?? '—')} pages</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* LLM classification */}
      {isLlm && (
        <div className="space-y-1.5 border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            LLM classification
          </p>
          <div className="space-y-1 text-xs">
            <div className="flex gap-2">
              <span className="text-muted-foreground w-24 shrink-0">Provider</span>
              <span>{String(cfg.provider ?? '—')}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-muted-foreground w-24 shrink-0">Model</span>
              <span>{String(cfg.model ?? '—')}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-muted-foreground w-24 shrink-0">Temperature</span>
              <span>{String(llmCfg.temperature ?? '—')}</span>
            </div>
            {typeof llmCfg.system_prompt === 'string' && llmCfg.system_prompt && (
              <div className="flex gap-2 items-start">
                <span className="text-muted-foreground w-24 shrink-0 mt-0.5">
                  System prompt
                </span>
                <Collapsible
                  open={promptExpanded}
                  onOpenChange={setPromptExpanded}
                  className="flex-1 min-w-0"
                >
                  <CollapsibleTrigger asChild>
                    <button className="text-left w-full hover:text-foreground">
                      {promptExpanded ? (
                        <span className="text-xs underline text-muted-foreground">Hide</span>
                      ) : (
                        <span className="block text-muted-foreground line-clamp-2 break-words">
                          {llmCfg.system_prompt.slice(0, 100)}
                          {llmCfg.system_prompt.length > 100 ? '…' : ''}
                        </span>
                      )}
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <pre className="mt-1 text-xs whitespace-pre-wrap break-words bg-muted rounded p-2 font-mono">
                      {llmCfg.system_prompt}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
