import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { it, expect, vi, beforeEach } from 'vitest'
import { AgentRunForm } from './AgentRunForm'
import type { AgentTool } from '@/types/agent'

vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({
    sourceDocuments: [{ id: 'sd-1', filename: 'invoice.pdf' }], isLoading: false,
  }),
}))
const startAgentRun = vi.fn<(projectId: string, data: unknown) => Promise<{ id: string }>>(
  async () => ({ id: 'run-1' })
)
vi.mock('@/api/agent', () => ({
  startAgentRun: (projectId: string, data: unknown) => startAgentRun(projectId, data),
}))

const tools: AgentTool[] = [{
  slug: 'parse.llamaparse', name: 'LlamaParse', category: 'parsing',
  description: '', runtimeInputs: [{ key: 'source_document_id',
    label: 'Source document', widget: 'source_document_picker' }],
  outputs: ['parsed_document_id'], configSchema: {}, configPanel: 'llamaparse',
}]
const definition = { nodes: [{ id: 'n1', tool: 'parse.llamaparse', config: {} }], edges: [] }

beforeEach(() => startAgentRun.mockClear())

it('derives a source-document field and starts a generic run', async () => {
  render(<AgentRunForm projectId="p1" definitionId="def-1"
                       definition={definition} tools={tools} onStarted={vi.fn()} />)
  await userEvent.selectOptions(await screen.findByLabelText(/source document/i), 'sd-1')
  await userEvent.click(screen.getByRole('button', { name: /run/i }))
  await waitFor(() => expect(startAgentRun).toHaveBeenCalledWith('p1', {
    agentDefinitionId: 'def-1', initialState: { source_document_id: 'sd-1' },
  }))
})
