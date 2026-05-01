import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ParsedDocumentPicker } from './ParsedDocumentPicker'

vi.mock('@/lib/parsed-documents', () => ({
  listParsedDocuments: vi.fn(),
}))

import { listParsedDocuments } from '@/lib/parsed-documents'

const docA = {
  id: 'pd-1',
  parseRunId: 'pr-1',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-1',
  sourceFilename: 'acme-msa.pdf',
  hasFullMarkdown: true,
  blockCount: 12,
  parsedAt: '2026-04-30T09:11:00Z',
}

const docB = {
  id: 'pd-2',
  parseRunId: 'pr-2',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-2',
  sourceFilename: 'vendor-form.pdf',
  hasFullMarkdown: true,
  blockCount: 8,
  parsedAt: '2026-04-30T11:48:00Z',
}

const olderDocA = {
  id: 'pd-3',
  parseRunId: 'pr-3',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-1',
  sourceFilename: 'acme-msa.pdf',
  hasFullMarkdown: true,
  blockCount: 10,
  parsedAt: '2026-04-29T14:32:00Z',
}

const defaultProps = {
  projectId: 'proj-1',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  representation: 'full_markdown' as const,
  selectedIds: [],
  onChange: vi.fn(),
}

describe('ParsedDocumentPicker', () => {
  beforeEach(() => {
    vi.mocked(listParsedDocuments).mockResolvedValue([docA, docB])
  })

  it('fetches with latestPerSource=true by default and shows both docs', async () => {
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument()
      expect(screen.getByText('vendor-form.pdf')).toBeInTheDocument()
    })
    expect(vi.mocked(listParsedDocuments)).toHaveBeenCalledWith('proj-1', {
      parser: 'llamaparse',
      parseConfigHash: 'abc',
      representation: 'full_markdown',
      latestPerSource: true,
    })
  })

  it('refetches with latestPerSource=false when the toggle is unchecked', async () => {
    vi.mocked(listParsedDocuments)
      .mockResolvedValueOnce([docA, docB])
      .mockResolvedValueOnce([docA, docB, olderDocA])

    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('checkbox', { name: /latest per source/i }))

    await waitFor(() =>
      expect(vi.mocked(listParsedDocuments)).toHaveBeenCalledWith('proj-1', {
        parser: 'llamaparse',
        parseConfigHash: 'abc',
        representation: 'full_markdown',
        latestPerSource: false,
      }),
    )
  })

  it('calls onChange with the doc id when a row checkbox is checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} onChange={onChange} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('checkbox', { name: 'acme-msa.pdf' }))

    expect(onChange).toHaveBeenCalledWith(['pr-1'])
  })

  it('filters rows by filename when search is typed', async () => {
    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText(/search by filename/i), 'vendor')

    expect(screen.queryByText('acme-msa.pdf')).not.toBeInTheDocument()
    expect(screen.getByText('vendor-form.pdf')).toBeInTheDocument()
  })
})
