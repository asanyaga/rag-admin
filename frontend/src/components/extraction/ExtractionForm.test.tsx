import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

describe('ExtractionForm', () => {
  it('calls onRun with parseRunId in request', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn().mockResolvedValue(undefined)
    render(
      <ExtractionForm
        parseRunId="parse-run-123"
        schemas={[schema]}
        extractors={[extractor]}
        onRun={onRun}
      />
    )
    const runButton = await screen.findByRole('button', { name: /run extraction/i })
    await user.click(runButton)
    await waitFor(() => {
      expect(onRun).toHaveBeenCalledWith(
        expect.objectContaining({ parseRunId: 'parse-run-123' })
      )
    })
  })
})
