import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

vi.mock('@/lib/exportCsv', () => ({
  exportResultToCsv: vi.fn(),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}))

vi.mock('@/hooks/useResultTransform', () => ({
  useResultTransform: () => ({
    catalog: [],
    loadCatalog: vi.fn(),
    preview: vi.fn(),
    apply: vi.fn(),
    previewData: null,
    flags: [],
    isLoading: false,
    error: null,
  }),
}))

import { exportResultToCsv } from '@/lib/exportCsv'

function buildResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return {
    id: 'result-1',
    documentId: 'doc-1',
    extractionSchemaId: 'schema-1',
    schemaDefinitionSnapshot: {},
    extractionMethod: 'llamaextract',
    config: null,
    structuredData: { invoice_number: 'INV-001' },
    extractionMetadata: { latency_ms: 1234, file_id: 'f-abc' },
    citations: null,
    providerResponseRaw: null,
    sourceParseRunId: 'run-1',
    status: 'completed',
    statusMessage: null,
    startedAt: '2026-01-01T00:00:00Z',
    timeoutMinutes: null,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function buildLlmResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      model: 'claude-opus-4-7',
      provider: 'anthropic',
      latency_ms: 17794,
      usage: { prompt_tokens: 3712, completion_tokens: 1830, total_tokens: 5542 },
      prompt_messages: [
        { role: 'system', content: 'You are an extraction assistant.' },
        {
          role: 'user',
          content:
            'Extract the following.\n<schema>{"type":"object"}</schema>\n<document>Invoice #001</document>',
        },
      ],
    },
    config: {
      structured_output_mode: 'json_schema',
      inject_block_ids: false,
      chunking: { strategy: 'none', citationLevel: 'auto' },
    },
    providerResponseRaw: { id: 'msg_001', content: [{ type: 'text', text: '{}' }] },
    ...overrides,
  })
}

function buildChunkedResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      chunkCount: 3,
      usage: { total_tokens: 12000 },
      scalarConflicts: [],
      // no model, provider, latency_ms, prompt_messages
    },
    config: {
      structured_output_mode: 'json_schema',
      chunking: { strategy: 'token_budget_pages', config: { maxInputTokens: 4000 }, citationLevel: 'auto' },
    },
    providerResponseRaw: null,
    ...overrides,
  })
}

describe('ExtractionResultViewer', () => {
  // ── Run Config panel ──────────────────────────────────────────────────────
  it('shows Run Config panel for all results', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Run Config')).toBeInTheDocument()
  })

  it('shows model and provider in Run Config for LLM results', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('claude-opus-4-7')).toBeInTheDocument()
    expect(screen.getByText('anthropic')).toBeInTheDocument()
  })

  it('shows formatted latency in Run Config for LLM results', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('17,794 ms')).toBeInTheDocument()
  })

  it('shows token counts in Run Config for LLM results', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('3,712')).toBeInTheDocument()
    expect(screen.getByText('1,830')).toBeInTheDocument()
    expect(screen.getByText('5,542')).toBeInTheDocument()
  })

  it('shows chunked run placeholder for model when model is absent', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getAllByText('Not available for chunked runs').length).toBeGreaterThan(0)
  })

  it('shows chunk count in Run Config for chunked results', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows chunking strategy in Run Config settings', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('token_budget_pages')).toBeInTheDocument()
  })

  it('shows max input tokens when chunking strategy is not none', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    await user.click(screen.getByRole('button', { name: /run config/i }))
    expect(screen.getByText('4,000')).toBeInTheDocument()
  })

  // ── Prompt panel ──────────────────────────────────────────────────────────
  it('shows Prompt panel for all results', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Prompt')).toBeInTheDocument()
  })

  it('shows System and User tabs in Prompt panel for LLM results with prompt_messages', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    await user.click(screen.getByRole('button', { name: /^prompt$/i }))
    expect(screen.getByRole('tab', { name: 'System' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'User' })).toBeInTheDocument()
  })

  it('shows system prompt content in System tab', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    await user.click(screen.getByRole('button', { name: /^prompt$/i }))
    expect(screen.getByText('You are an extraction assistant.')).toBeInTheDocument()
  })

  it('shows chunking unavailable message in Prompt panel for chunked results', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    await user.click(screen.getByRole('button', { name: /^prompt$/i }))
    expect(
      screen.getByText(/Prompt not available.*chunking/i)
    ).toBeInTheDocument()
  })

  // ── LLM Response panel ────────────────────────────────────────────────────
  it('shows LLM Response panel when providerResponseRaw is present', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: { invoice_number: 'INV-001' } } })}
      />
    )
    expect(screen.getByText('LLM Response')).toBeInTheDocument()
  })

  it('does not show LLM Response panel when providerResponseRaw is null', () => {
    render(<ExtractionResultViewer result={buildResult({ providerResponseRaw: null })} />)
    expect(screen.queryByText('LLM Response')).not.toBeInTheDocument()
  })

  it('does not show LLM Response panel for chunked runs', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.queryByText('LLM Response')).not.toBeInTheDocument()
  })

  it('shows Raw label when providerResponseRaw contains raw_content string', async () => {
    const user = userEvent.setup()
    render(
      <ExtractionResultViewer
        result={buildResult({
          providerResponseRaw: { raw_content: 'this is not json' },
        })}
      />
    )
    await user.click(screen.getByRole('button', { name: /llm response/i }))
    expect(screen.getByText('Raw (non-JSON) response')).toBeInTheDocument()
    expect(screen.getByText('this is not json')).toBeInTheDocument()
  })

  // ── Legacy panel absence ──────────────────────────────────────────────────
  it('does not render old "Extraction Metadata" panel text', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText('Extraction Metadata')).not.toBeInTheDocument()
  })

  it('does not render old "Provider Response" panel text', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: {} } })}
      />
    )
    expect(screen.queryByText('Provider Response')).not.toBeInTheDocument()
  })

  it('does not show old metadata label', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText(/citations \/ reasoning/i)).not.toBeInTheDocument()
  })
})

// ── Chunk Details fixtures ────────────────────────────────────────────────────

function buildChunkedResultWithDetails(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      chunkCount: 2,
      usage: { total_tokens: 6400 },
      model: 'claude-opus-4-7',
      provider: 'anthropic',
      latency_ms: 2700,
      chunks: [
        {
          chunkIndex: 0,
          pageIndices: [0, 1, 2],
          promptMessages: [
            { role: 'system', content: 'Shared system prompt.' },
            {
              role: 'user',
              content:
                'Extract.\n<schema>{"type":"object"}</schema>\n<document>Page 1 content</document>',
            },
          ],
          providerResponseRaw: { id: 'r1', answer: 'chunk-1-response' },
          structuredData: { invoice: 'INV-001' },
          usage: { prompt_tokens: 3000, completion_tokens: 500, total_tokens: 3500 },
          latencyMs: 1500,
        },
        {
          chunkIndex: 1,
          pageIndices: [3, 4],
          promptMessages: [
            { role: 'system', content: 'Shared system prompt.' },
            {
              role: 'user',
              content:
                'Extract.\n<schema>{"type":"object"}</schema>\n<document>Page 2 content</document>',
            },
          ],
          providerResponseRaw: { id: 'r2', answer: 'chunk-2-response' },
          structuredData: { invoice: 'INV-002' },
          usage: { prompt_tokens: 2400, completion_tokens: 500, total_tokens: 2900 },
          latencyMs: 1200,
        },
      ],
    },
    providerResponseRaw: null,
    ...overrides,
  })
}

describe('Chunk Details panel', () => {
  it('does not show Chunk Details panel when no chunks in metadata', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.queryByRole('button', { name: /chunk details/i })).not.toBeInTheDocument()
  })

  it('shows Chunk Details panel trigger when chunks are present', () => {
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    expect(screen.getByRole('button', { name: /chunk details/i })).toBeInTheDocument()
  })

  it('chunk list shows page range and token count for each chunk', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText('Chunk 1')).toBeInTheDocument()
    expect(screen.getByText(/pp\. 1–3/)).toBeInTheDocument()
    expect(screen.getByText(/3,500 tokens/)).toBeInTheDocument()
    expect(screen.getByText('Chunk 2')).toBeInTheDocument()
    expect(screen.getByText(/pp\. 4–5/)).toBeInTheDocument()
  })

  it('system prompt section carries identical-across-all-chunks note', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText(/Identical across all chunks/i)).toBeInTheDocument()
  })

  it('extracted pre-merge section carries raw-output note', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText(/Raw output before conflict resolution/i)).toBeInTheDocument()
  })

  it('selecting a different chunk updates the detail pane', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    // Chunk 1 is selected by default
    expect(screen.getByText('Page 1 content')).toBeInTheDocument()
    // Click chunk 2 in the list
    await user.click(screen.getByRole('button', { name: /chunk 2/i }))
    expect(screen.getByText('Page 2 content')).toBeInTheDocument()
  })
})

describe('Export CSV button', () => {
  it('renders when result is completed with structuredData', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
  })

  it('does not render when result is pending', () => {
    render(<ExtractionResultViewer result={buildResult({ status: 'pending', structuredData: null })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('does not render when structuredData is null', () => {
    render(<ExtractionResultViewer result={buildResult({ structuredData: null })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('does not render when structuredData is empty', () => {
    render(<ExtractionResultViewer result={buildResult({ structuredData: {} })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('calls exportResultToCsv with structuredData and filename on click', async () => {
    const user = userEvent.setup()
    render(
      <ExtractionResultViewer
        result={buildResult({ id: 'abcdef12-0000-0000-0000-000000000000' })}
        schemaName="My Schema"
      />
    )
    await user.click(screen.getByRole('button', { name: /export csv/i }))
    expect(exportResultToCsv).toHaveBeenCalledWith(
      { invoice_number: 'INV-001' },
      'My Schema_abcdef12.csv'
    )
  })

  it('uses "extraction" as fallback filename when schemaName is not provided', async () => {
    const user = userEvent.setup()
    render(
      <ExtractionResultViewer
        result={buildResult({ id: 'abcdef12-0000-0000-0000-000000000000' })}
      />
    )
    await user.click(screen.getByRole('button', { name: /export csv/i }))
    expect(exportResultToCsv).toHaveBeenCalledWith(
      { invoice_number: 'INV-001' },
      'extraction_abcdef12.csv'
    )
  })
})
