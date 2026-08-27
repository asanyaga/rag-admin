import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { NodeConfigPanel } from './NodeConfigPanel'
import type { AgentTool } from '@/types/agent'

const llamaTool: AgentTool = {
  slug: 'parse.llamaparse', name: 'LlamaParse', category: 'parsing',
  description: 'Parse with LlamaParse', runtimeInputs: [], outputs: [],
  configSchema: {}, configPanel: 'llamaparse',
}

const node = {
  id: 'n1', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.llamaparse', label: 'LlamaParse', category: 'parsing',
          config: { parser: 'llamaparse', parse_config: { tier: 'agentic' } } },
} as never

describe('NodeConfigPanel', () => {
  it('renders the real LlamaParse panel for a parsing tool', () => {
    render(<NodeConfigPanel node={node} tools={[llamaTool]}
                            onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
    // LlamaParseConfig renders a "Tier" label — assert its presence
    expect(screen.getByText(/tier/i)).toBeInTheDocument()
  })
})
