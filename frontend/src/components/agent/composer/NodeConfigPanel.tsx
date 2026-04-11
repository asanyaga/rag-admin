import { useMemo } from 'react'
import type { Node } from '@xyflow/react'
import type { AgentTool } from '@/types/agent'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { X, Settings2 } from 'lucide-react'

interface NodeConfigPanelProps {
  node: Node
  tools: AgentTool[]
  onUpdateConfig: (nodeId: string, config: Record<string, unknown>) => void
  onClose: () => void
}

export function NodeConfigPanel({
  node,
  tools,
  onUpdateConfig,
  onClose,
}: NodeConfigPanelProps) {
  const tool = useMemo(
    () => tools.find((t) => t.slug === node.data.toolSlug),
    [tools, node.data.toolSlug]
  )

  const config = (node.data.config ?? {}) as Record<string, unknown>
  const schema = tool?.configSchema as
    | { properties?: Record<string, { type?: string; description?: string; enum?: string[]; default?: unknown }> }
    | undefined

  const properties = schema?.properties ?? {}
  const hasConfig = Object.keys(properties).length > 0

  const handleChange = (key: string, value: string) => {
    onUpdateConfig(node.id, { ...config, [key]: value })
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">Node Settings</span>
        </div>
        <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-1">
        <div className="text-sm font-medium">{node.data.label as string}</div>
        <div className="text-xs text-muted-foreground">
          {tool?.description ?? 'No description'}
        </div>
      </div>

      {tool && (
        <div className="space-y-1 text-xs">
          <div>
            <span className="font-medium text-muted-foreground">Inputs: </span>
            <span className="font-mono">{tool.inputKeys.join(', ') || 'none'}</span>
          </div>
          <div>
            <span className="font-medium text-muted-foreground">Outputs: </span>
            <span className="font-mono">{tool.outputKeys.join(', ') || 'none'}</span>
          </div>
        </div>
      )}

      {hasConfig && (
        <>
          <Separator />
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Configuration
            </div>
            {Object.entries(properties).map(([key, prop]) => (
              <div key={key} className="space-y-1">
                <Label className="text-xs">{key}</Label>
                {prop.enum ? (
                  <select
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    value={(config[key] as string) ?? prop.default ?? ''}
                    onChange={(e) => handleChange(key, e.target.value)}
                  >
                    {prop.enum.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    className="h-8 text-sm"
                    value={(config[key] as string) ?? ''}
                    placeholder={prop.description ?? key}
                    onChange={(e) => handleChange(key, e.target.value)}
                  />
                )}
                {prop.description && (
                  <p className="text-[10px] text-muted-foreground">
                    {prop.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {!hasConfig && (
        <>
          <Separator />
          <p className="text-xs text-muted-foreground">
            This tool has no configurable options.
          </p>
        </>
      )}
    </div>
  )
}
