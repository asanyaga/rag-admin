import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

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
