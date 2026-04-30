import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IndexCreateDialog } from './IndexCreateDialog'
import type { DocumentListItem } from '@/types/document'

vi.mock('@/lib/parsed-documents', () => ({
  resolveLatestParsedDocsForDocuments: vi.fn(),
}))
import { resolveLatestParsedDocsForDocuments } from '@/lib/parsed-documents'

beforeEach(() => {
  vi.mocked(resolveLatestParsedDocsForDocuments).mockResolvedValue({
    parser: 'llamaparse',
    parseConfigHash: 'h'.repeat(64),
    parsedDocumentIds: ['parsed-doc-1'],
  })
})

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  projectId: 'proj-1',
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onPreviewChunks: vi.fn().mockResolvedValue({
    totalChunksEstimate: 0,
    avgChunkSizeChars: 0,
    avgChunkSizeTokens: 0,
    minChunkSizeChars: 0,
    maxChunkSizeChars: 0,
    previewChunks: [],
  }),
  documents: [],
}

const readyDocument: DocumentListItem = {
  id: 'doc-1',
  projectId: 'proj-1',
  folderId: null,
  sourceType: 'upload',
  title: 'Test Document',
  description: null,
  status: 'ready',
  statusMessage: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

describe('IndexCreateDialog — chunking config', () => {
  it('shows text chunking fields by default (raw_text source)', () => {
    render(<IndexCreateDialog {...defaultProps} />)
    expect(screen.getByLabelText('Chunk Size')).toBeInTheDocument()
    expect(screen.getByLabelText('Overlap')).toBeInTheDocument()
    expect(screen.queryByText('Heading split level')).not.toBeInTheDocument()
    expect(screen.queryByText('Max section size')).not.toBeInTheDocument()
  })

  it('shows markdown controls and hides text controls when full_markdown selected', async () => {
    const user = userEvent.setup()
    render(<IndexCreateDialog {...defaultProps} />)

    // Click the "full_markdown" option in the source representation control
    const fullMarkdownButton = screen.getByRole('radio', { name: /full markdown/i })
    await user.click(fullMarkdownButton)

    expect(screen.getByText('Heading split level')).toBeInTheDocument()
    expect(screen.getByText('Max section size')).toBeInTheDocument()
    expect(screen.queryByLabelText('Chunk Size')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Overlap')).not.toBeInTheDocument()
  })
})

describe('IndexCreateDialog — chunk preview', () => {
  it('enables Preview Chunks button when full_markdown is selected and a document is pre-selected', async () => {
    const user = userEvent.setup()
    render(
      <IndexCreateDialog
        {...defaultProps}
        documents={[readyDocument]}
        preselectedDocumentIds={['doc-1']}
      />
    )

    // Select full_markdown source
    const fullMarkdownButton = screen.getByRole('radio', { name: /full markdown/i })
    await user.click(fullMarkdownButton)

    // Preview Chunks button should be enabled (band-aid is lifted)
    const previewButton = screen.getByRole('button', { name: /preview chunks/i })
    expect(previewButton).not.toBeDisabled()
  })

  it('calls onPreviewChunks with full_markdown source representation when Preview Chunks is clicked', async () => {
    const onPreviewChunks = vi.fn().mockResolvedValue({
      totalChunksEstimate: 2,
      avgChunkSizeChars: 100,
      avgChunkSizeTokens: 25,
      minChunkSizeChars: 80,
      maxChunkSizeChars: 120,
      previewChunks: [],
    })
    const user = userEvent.setup()
    render(
      <IndexCreateDialog
        {...defaultProps}
        onPreviewChunks={onPreviewChunks}
        documents={[readyDocument]}
        preselectedDocumentIds={['doc-1']}
      />
    )

    // Select full_markdown source
    const fullMarkdownButton = screen.getByRole('radio', { name: /full markdown/i })
    await user.click(fullMarkdownButton)

    // Click Preview Chunks
    const previewButton = screen.getByRole('button', { name: /preview chunks/i })
    await user.click(previewButton)

    // onPreviewChunks should have been called with the resolved parsedDocumentId and full_markdown config
    expect(onPreviewChunks).toHaveBeenCalledOnce()
    const [calledParsedDocumentId, calledConfig] = onPreviewChunks.mock.calls[0]
    expect(calledParsedDocumentId).toBe('parsed-doc-1')
    expect(calledConfig).toMatchObject({ sourceRepresentation: 'full_markdown' })
  })
})
