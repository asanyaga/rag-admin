import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtractionForm } from './ExtractionForm'
import type { ExtractionSchema, ExtractorInfo } from '@/types/extraction'

const schema: ExtractionSchema = {
  id: 'schema-1',
  projectId: 'proj-1',
  name: 'Test Schema',
  description: null,
  schemaDefinition: {},
  extractionTarget: 'PER_DOC',
  createdBy: 'user-1',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

const extractor: ExtractorInfo = {
  extractionMethod: 'llamaextract',
  name: 'LlamaExtract',
  description: 'LlamaExtract via LlamaCloud',
  configSchema: null,
  configured: true,
}

const defaultProps = {
  defaultParser: 'simple',
  defaultParserConfig: {},
  schemas: [schema],
  extractors: [extractor],
}

describe('ExtractionForm', () => {
  it('calls onRun with parseConfig and extractionConfig in request', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn().mockResolvedValue(undefined)
    render(<ExtractionForm {...defaultProps} onRun={onRun} />)
    const runButton = screen.getByRole('button', { name: /run extraction/i })
    await user.click(runButton)
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        parseConfig: expect.objectContaining({ parser: 'simple', representationKind: 'extract_rich' }),
        extractionConfig: expect.objectContaining({ extractionSchemaId: 'schema-1' }),
      })
    )
  })

  it('disables Run button and shows warning when selected extractor is not configured', () => {
    const unconfigured: ExtractorInfo = { ...extractor, configured: false }
    render(<ExtractionForm {...defaultProps} extractors={[unconfigured]} onRun={vi.fn()} />)
    expect(screen.getByRole('button', { name: /run extraction/i })).toBeDisabled()
    expect(screen.getByText(/not configured/i)).toBeInTheDocument()
  })

  it('shows extraction target and confidence scores controls for llamaextract', () => {
    render(<ExtractionForm {...defaultProps} onRun={vi.fn()} />)
    expect(screen.getByLabelText(/target/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confidence scores/i)).toBeInTheDocument()
  })

  it('includes confidence_scores in config when checked', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn().mockResolvedValue(undefined)
    render(<ExtractionForm {...defaultProps} onRun={onRun} />)
    await user.click(screen.getByLabelText(/confidence scores/i))
    await user.click(screen.getByRole('button', { name: /run extraction/i }))
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        extractionConfig: expect.objectContaining({
          config: expect.objectContaining({ confidence_scores: true }),
        }),
      })
    )
  })

  it('includes extraction_target in config for llamaextract', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn().mockResolvedValue(undefined)
    render(<ExtractionForm {...defaultProps} onRun={onRun} />)
    await user.click(screen.getByRole('button', { name: /run extraction/i }))
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        extractionConfig: expect.objectContaining({
          config: expect.objectContaining({ extraction_target: 'PER_DOC' }),
        }),
      })
    )
  })
})
