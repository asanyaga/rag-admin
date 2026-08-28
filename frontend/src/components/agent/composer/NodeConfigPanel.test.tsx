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

const doclingTool = {
  slug: 'parse.docling', name: 'Docling', category: 'parsing',
  description: '', runtimeInputs: [], outputs: [],
  configSchema: {}, configPanel: 'docling',
} as AgentTool

const doclingNode = {
  id: 'n2', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.docling', label: 'Docling', category: 'parsing',
          config: { parser: 'docling', parse_config: {} } },
} as never

const simpleTool = {
  slug: 'parse.simple', name: 'Simple', category: 'parsing',
  description: '', runtimeInputs: [], outputs: [],
  configSchema: { type: 'object', properties: {
    representation_kind: { type: 'string', default: 'extract_rich' },
    parse_config: { type: 'object' },
  } },
  configPanel: null,
} as AgentTool

const simpleNode = {
  id: 'n3', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.simple', label: 'Simple', category: 'parsing', config: {} },
} as never

describe('NodeConfigPanel', () => {
  it('renders the real LlamaParse panel for a parsing tool', () => {
    render(<NodeConfigPanel node={node} tools={[llamaTool]}
                            onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
    // LlamaParseConfig renders a "Tier" label — assert its presence
    expect(screen.getByText(/tier/i)).toBeInTheDocument()
  })

  it('renders the real Docling panel for a docling parsing node', () => {
    render(<NodeConfigPanel node={doclingNode} tools={[doclingTool]}
                            onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
    // DoclingConfig renders a "Pipeline" control
    expect(screen.getByText(/pipeline/i)).toBeInTheDocument()
  })

  it('shows a no-options message for a panel-less parsing node (Simple)', () => {
    render(<NodeConfigPanel node={simpleNode} tools={[simpleTool]}
                            onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/no options/i)).toBeInTheDocument()
    // must NOT fall through to the generic schema field renderer
    expect(screen.queryByText(/parse_config/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/representation_kind/i)).not.toBeInTheDocument()
  })
})
