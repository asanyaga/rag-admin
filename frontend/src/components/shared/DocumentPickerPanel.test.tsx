import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentPickerPanel } from './DocumentPickerPanel'
import type { DocumentListItem } from '@/types/document'
import type { Folder } from '@/types/folder'

const docs: DocumentListItem[] = [
  {
    id: 'd1',
    projectId: 'p1',
    folderId: null,
    sourceType: 'upload',
    title: 'Alpha.pdf',
    description: null,
    status: 'ready',
    statusMessage: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  },
  {
    id: 'd2',
    projectId: 'p1',
    folderId: null,
    sourceType: 'upload',
    title: 'Beta.pdf',
    description: null,
    status: 'processing',
    statusMessage: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  },
]

const folders: Folder[] = [
  {
    id: 'f1',
    projectId: 'p1',
    name: 'Invoices',
    description: null,
    tags: [],
    documentCount: 1,
    createdBy: 'u1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  },
]

describe('DocumentPickerPanel', () => {
  it('renders document list', () => {
    render(
      <DocumentPickerPanel
        documents={docs}
        folders={folders}
        isLoading={false}
        selectedDocumentId={null}
        onSelect={vi.fn()}
        onUploadClick={vi.fn()}
      />,
    )
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    expect(screen.getByText('Beta.pdf')).toBeInTheDocument()
  })

  it('calls onSelect with document id when ready row clicked', async () => {
    const onSelect = vi.fn()
    render(
      <DocumentPickerPanel
        documents={docs}
        folders={folders}
        isLoading={false}
        selectedDocumentId={null}
        onSelect={onSelect}
        onUploadClick={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByText('Alpha.pdf'))
    expect(onSelect).toHaveBeenCalledWith('d1')
  })

  it('does not call onSelect for processing documents', async () => {
    const onSelect = vi.fn()
    render(
      <DocumentPickerPanel
        documents={docs}
        folders={folders}
        isLoading={false}
        selectedDocumentId={null}
        onSelect={onSelect}
        onUploadClick={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByText('Beta.pdf'))
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('filters list by search text', async () => {
    render(
      <DocumentPickerPanel
        documents={docs}
        folders={folders}
        isLoading={false}
        selectedDocumentId={null}
        onSelect={vi.fn()}
        onUploadClick={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByPlaceholderText('Search documents...'), 'Alpha')
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    expect(screen.queryByText('Beta.pdf')).not.toBeInTheDocument()
  })

  it('calls onUploadClick when upload button clicked', async () => {
    const onUploadClick = vi.fn()
    render(
      <DocumentPickerPanel
        documents={docs}
        folders={folders}
        isLoading={false}
        selectedDocumentId={null}
        onSelect={vi.fn()}
        onUploadClick={onUploadClick}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /upload document/i }))
    expect(onUploadClick).toHaveBeenCalled()
  })
})
