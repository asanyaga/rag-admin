import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { AgentRunDetail } from './AgentRunDetail'
import type { AgentRun, AgentDefinition, AgentTool } from '@/types/agent'

const parseTool: AgentTool = {
  slug: 'parse.llamaparse',
  name: 'LlamaParse',
  category: 'parsing',
  description: '',
  runtimeInputs: [],
  outputs: [
    'parse_run_id',
    'parsed_document_id',
    'page_count',
    'text_len',
    'failed_page_count',
    'block_count',
  ],
  configSchema: {},
  configPanel: 'llamaparse',
}

const definition: AgentDefinition = {
  id: 'def-1',
  projectId: 'p1',
  name: 'Parse',
  description: null,
  definition: { nodes: [{ id: 'n1', tool: 'parse.llamaparse', config: {} }], edges: [] },
  createdBy: 'u',
  createdAt: '2026-08-27T00:00:00Z',
  updatedAt: '2026-08-27T00:00:00Z',
}

const run: AgentRun = {
  id: 'r1',
  projectId: 'p1',
  agentDefinitionId: 'def-1',
  status: 'completed',
  statusMessage: null,
  initialState: {},
  currentState: {
    source_document_id: 'sd-1',
    parse_run_id: 'pr-1',
    parsed_document_id: 'pd-9',
    page_count: 3,
    text_len: 100,
    failed_page_count: 0,
    block_count: 12,
    current_step: 'parsed',
  },
  currentNode: null,
  threadId: null,
  createdBy: 'u',
  createdAt: '2026-08-27T00:00:00Z',
  updatedAt: '2026-08-27T00:00:00Z',
}

describe('AgentRunDetail', () => {
  it('renders parse output data for a completed parse run', () => {
    render(
      <AgentRunDetail
        run={run}
        agentDefinition={definition}
        tools={[parseTool]}
        isLoading={false}
        isResuming={false}
        error={null}
        onResume={vi.fn()}
      />
    )
    // The parse run produced outputs — it must NOT report "no output data".
    expect(screen.queryByText(/no output data/i)).not.toBeInTheDocument()
    // The contract's output keys are surfaced as the run's results.
    expect(screen.getByText(/parsed_document_id/)).toBeInTheDocument()
    expect(screen.getByText(/pd-9/)).toBeInTheDocument()
    expect(screen.getByText(/block_count/)).toBeInTheDocument()
  })
})
