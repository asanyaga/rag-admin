import { Button } from '@/components/ui/button'
import { AgentFlowGraph } from './AgentFlowGraph'
import { Plus, Trash2, Bot } from 'lucide-react'
import type { AgentType, AgentConfig } from '@/types/agent'

interface AgentSetupProps {
  agentTypes: AgentType[]
  configs?: AgentConfig[]
  onEnable: (agentType: string) => Promise<void>
  onRemove?: (configId: string) => Promise<void>
}

export function AgentSetup({
  agentTypes,
  configs = [],
  onEnable,
  onRemove,
}: AgentSetupProps) {
  const enabledSlugs = new Set(configs.map((c) => c.agentType))
  const availableTypes = agentTypes.filter((t) => !enabledSlugs.has(t.slug))

  return (
    <div className="space-y-4">
      {/* Enabled agents */}
      {configs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium">Enabled Agents</h2>
          {configs.map((config) => {
            const agentType = agentTypes.find((t) => t.slug === config.agentType)
            return (
              <div key={config.id} className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Bot className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">
                        {agentType?.name || config.agentType}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {agentType?.description}
                      </p>
                    </div>
                  </div>
                  {onRemove && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRemove(config.id)}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  )}
                </div>
                {agentType && (
                  <AgentFlowGraph nodes={agentType.nodes} height={100} />
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Available to add */}
      {availableTypes.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">
            {configs.length === 0
              ? 'No agents configured for this project'
              : 'Add More Agents'}
          </h2>
          {configs.length === 0 && (
            <p className="text-sm text-muted-foreground mb-3">
              Enable an agent type to get started with automated workflows.
            </p>
          )}
          {availableTypes.map((agentType) => (
            <div key={agentType.slug} className="rounded-lg border border-dashed p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bot className="h-4 w-4 text-muted-foreground/50" />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      {agentType.name}
                    </p>
                    <p className="text-xs text-muted-foreground/70">
                      {agentType.description}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEnable(agentType.slug)}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Enable
                </Button>
              </div>
              <AgentFlowGraph nodes={agentType.nodes} height={100} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
