import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ParsedDocumentPane } from './ParsedDocumentPane'
import type { ParsedDocumentDetail } from '@/types/cdm'

const makeDoc = (overrides = {}): ParsedDocumentDetail => ({
  parseRunId: 'run-1',
  sourceDocumentId: 'src-1',
  pageCount: 1,
  blockCount: 2,
  fullText: 'hello world',
  fullMarkdown: '# Hello',
  content: {
    pages: [{ index: 0 }],
    blocks: [
      { id: 'b1', page_index: 0, role: 'paragraph', text: 'Block one' },
      { id: 'b2', page_index: 0, role: 'table', text: 'Block two' },
    ],
  },
  ...overrides,
})

describe('ParsedDocumentPane', () => {
  it('renders block roles', () => {
    render(<ParsedDocumentPane parsedDocument={makeDoc()} />)
    expect(screen.getAllByText('paragraph').length).toBeGreaterThan(0)
    expect(screen.getAllByText('table').length).toBeGreaterThan(0)
  })

  it('expands the selected block when selectedBlockId is provided', async () => {
    render(
      <ParsedDocumentPane
        parsedDocument={makeDoc()}
        selectedBlockId="b1"
      />
    )
    // When expanded, 'Block one' appears in both the trigger preview and the content
    expect(screen.getAllByText('Block one').length).toBeGreaterThan(1)
  })

  it('calls onBlockSelect with block id when a block row is clicked', async () => {
    const onBlockSelect = vi.fn()
    render(
      <ParsedDocumentPane
        parsedDocument={makeDoc()}
        onBlockSelect={onBlockSelect}
      />
    )
    // triggers[0] is the page header; triggers[1] is the first block row (b1)
    const triggers = screen.getAllByRole('button')
    await userEvent.click(triggers[1])
    expect(onBlockSelect).toHaveBeenCalledWith('b1')
  })

  it('renders loading state', () => {
    render(<ParsedDocumentPane parsedDocument={undefined} isLoading />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })
})
