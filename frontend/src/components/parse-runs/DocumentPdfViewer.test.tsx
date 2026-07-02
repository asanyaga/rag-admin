import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentPdfViewer } from './DocumentPdfViewer'
import type { Block } from '@/types/cdm'

vi.mock('react-pdf', () => ({
  Document: ({
    children,
    onLoadSuccess,
  }: {
    children: React.ReactNode
    onLoadSuccess?: (arg: { numPages: number }) => void
  }) => {
    onLoadSuccess?.({ numPages: 2 })
    return <div data-testid="pdf-document">{children}</div>
  },
  Page: ({ pageNumber }: { pageNumber: number }) => (
    <div data-testid={`pdf-page-${pageNumber}`} style={{ width: 600, height: 800 }} />
  ),
  pdfjs: { GlobalWorkerOptions: { workerSrc: '' } },
}))

vi.mock('@/api/client', () => ({ getAccessToken: () => 'test-token' }))

const makeBlocks = (): Block[] => [
  {
    id: 'b1',
    page_index: 0,
    role: 'text',
    text: 'Hello',
    bbox: { x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.2 },
  },
  {
    id: 'b2',
    page_index: 1,
    role: 'table',
    text: 'Table data',
    bbox: { x0: 0.2, y0: 0.3, x1: 0.8, y1: 0.6 },
  },
  {
    id: 'b3',
    page_index: 0,
    role: 'title',
    text: 'Title — no bbox',
    // intentionally no bbox
  },
]

describe('DocumentPdfViewer', () => {
  it('renders the pdf document container', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.getByTestId('pdf-document')).toBeInTheDocument()
  })

  it('renders bbox rects for blocks that have bboxes', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.getByTestId('bbox-rect-b1')).toBeInTheDocument()
    expect(screen.getByTestId('bbox-rect-b2')).toBeInTheDocument()
  })

  it('does not render a rect for blocks without a bbox', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.queryByTestId('bbox-rect-b3')).not.toBeInTheDocument()
  })

  it('calls onBlockSelect with the block id when a rect is clicked', async () => {
    const onBlockSelect = vi.fn()
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId={null}
        onBlockSelect={onBlockSelect}
      />
    )
    await userEvent.click(screen.getByTestId('bbox-rect-b1'))
    expect(onBlockSelect).toHaveBeenCalledWith('b1')
  })

  it('gives the selected block a higher fill opacity', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId="b1"
        onBlockSelect={vi.fn()}
      />
    )
    const rect = screen.getByTestId('bbox-rect-b1')
    expect(rect.getAttribute('fill-opacity')).toBe('0.5')
  })

  it('unselected blocks have lower fill opacity', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={makeBlocks()}
        selectedBlockId="b1"
        onBlockSelect={vi.fn()}
      />
    )
    const rect = screen.getByTestId('bbox-rect-b2')
    expect(Number(rect.getAttribute('fill-opacity'))).toBeLessThan(0.5)
  })
})
