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
vi.mock('@/hooks/useDocuments', () => ({
  useDocuments: () => ({ documents: [{ id: 'doc-1', title: 'Invoice', status: 'ready' }], isLoading: false }),
}))
vi.mock('@/hooks/useExtractionSchemas', () => ({
  useExtractionSchemas: () => ({ schemas: [{ id: 'sch-1', name: 'Invoice schema' }], isLoading: false }),
}))
const startAgentRun = vi.fn<(projectId: string, data: unknown) => Promise<{ id: string }>>(
  async () => ({ id: 'run-1' })
)
vi.mock('@/api/agent', () => ({
  startAgentRun: (projectId: string, data: unknown) => startAgentRun(projectId, data),
}))
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: { error: (...args: unknown[]) => toastError(...args), success: vi.fn() },
}))

const tools: AgentTool[] = [{
  slug: 'parse.llamaparse', name: 'LlamaParse', category: 'parsing',
  description: '', runtimeInputs: [{ key: 'source_document_id',
    label: 'Source document', widget: 'source_document_picker', source: 'form' }],
  outputs: ['parsed_document_id'], configSchema: {}, configPanel: 'llamaparse',
}]
const definition = { nodes: [{ id: 'n1', tool: 'parse.llamaparse', config: {} }], edges: [] }

beforeEach(() => {
  startAgentRun.mockClear()
  toastError.mockClear()
})

it('derives a source-document field and starts a generic run', async () => {
  render(<AgentRunForm projectId="p1" definitionId="def-1"
                       definition={definition} tools={tools} onStarted={vi.fn()} />)
  await userEvent.selectOptions(await screen.findByLabelText(/source document/i), 'sd-1')
  await userEvent.click(screen.getByRole('button', { name: /run/i }))
  await waitFor(() => expect(startAgentRun).toHaveBeenCalledWith('p1', {
    agentDefinitionId: 'def-1', initialState: { source_document_id: 'sd-1' },
  }))
})

it('shows a toast and re-enables the button when starting a run fails', async () => {
  startAgentRun.mockRejectedValueOnce(new Error('boom'))
  const onStarted = vi.fn()
  render(<AgentRunForm projectId="p1" definitionId="def-1"
                       definition={definition} tools={tools} onStarted={onStarted} />)
  await userEvent.selectOptions(await screen.findByLabelText(/source document/i), 'sd-1')
  const runButton = screen.getByRole('button', { name: /run/i })
  await userEvent.click(runButton)

  await waitFor(() => expect(toastError).toHaveBeenCalledWith('Failed to start run', {
    description: 'boom',
  }))
  expect(onStarted).not.toHaveBeenCalled()
  await waitFor(() => expect(runButton).not.toBeDisabled())
})

const extractTools: AgentTool[] = [
  { slug: 'llamaextract', name: 'LlamaExtract', category: 'extraction', description: '',
    runtimeInputs: [
      { key: 'document_id', label: 'Document', widget: 'document_picker', source: 'form' },
      { key: 'extraction_schema_id', label: 'Schema', widget: 'extraction_schema_picker', source: 'form' }],
    outputs: ['extracted_data'], configSchema: {}, configPanel: null },
  { slug: 'export', name: 'Export', category: 'export', description: '',
    runtimeInputs: [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    outputs: ['exported'], configSchema: {}, configPanel: null },
]
const extractDef = { nodes: [
  { id: 'e', tool: 'llamaextract' }, { id: 'x', tool: 'export' }],
  edges: [{ source: 'e', target: 'x' }] }

it('prompts document + schema for an extract chain and starts a generic run', async () => {
  render(<AgentRunForm projectId="p1" definitionId="def-1" definition={extractDef}
                       tools={extractTools} onStarted={vi.fn()} />)
  await userEvent.selectOptions(await screen.findByLabelText(/document/i), 'doc-1')
  await userEvent.selectOptions(screen.getByLabelText(/schema/i), 'sch-1')
  await userEvent.click(screen.getByRole('button', { name: /run/i }))
  await waitFor(() => expect(startAgentRun).toHaveBeenCalledWith('p1', {
    agentDefinitionId: 'def-1',
    initialState: { document_id: 'doc-1', extraction_schema_id: 'sch-1' },
  }))
})

it('disables Run when the graph has an unmet upstream input', () => {
  const loneExport = { nodes: [{ id: 'x', tool: 'export' }], edges: [] }
  render(<AgentRunForm projectId="p1" definitionId="def-1" definition={loneExport}
                       tools={extractTools} onStarted={vi.fn()} />)
  expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  expect(screen.getByText(/needs .*extracted data/i)).toBeInTheDocument()
})
