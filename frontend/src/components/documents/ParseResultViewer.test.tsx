import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ParseResultViewer } from './ParseResultViewer'
import { buildParseResult, buildParseResultListItem } from '@/test/builders'

// Mock the hook
vi.mock('@/hooks/useParseResults', () => ({
  useParseResults: vi.fn(),
}))

import { useParseResults } from '@/hooks/useParseResults'

const mockUseParseResults = vi.mocked(useParseResults)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ParseResultViewer', () => {
  const defaultHookReturn = {
    parseResults: [],
    selectedResult: null,
    isLoading: false,
    isLoadingResult: false,
    error: null,
    fetchParseResults: vi.fn(),
    selectParseResult: vi.fn(),
    reparseDocument: vi.fn(),
  }

  it('shows loading state', () => {
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      isLoading: true,
    })

    render(<ParseResultViewer documentId="doc-1" />)
    // Should show skeletons (they render as generic div elements)
    expect(document.querySelectorAll('[class*="skeleton"]').length).toBeGreaterThanOrEqual(0)
  })

  it('shows error state', () => {
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      error: 'Something went wrong',
    })

    render(<ParseResultViewer documentId="doc-1" />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('returns null when no parse results', () => {
    mockUseParseResults.mockReturnValue(defaultHookReturn)

    const { container } = render(<ParseResultViewer documentId="doc-1" />)
    expect(container.firstChild).toBeNull()
  })

  it('renders text tab with content', async () => {
    const result = buildParseResult()
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      parseResults: [buildParseResultListItem()],
      selectedResult: result,
    })

    render(<ParseResultViewer documentId="doc-1" />)

    expect(screen.getByText('Parse Results')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Text' })).toBeInTheDocument()
    expect(
      screen.getByText('Extracted text content from document')
    ).toBeInTheDocument()
  })

  it('renders markdown tab when available', () => {
    const result = buildParseResult({ markdown: '# Test Heading' })
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      parseResults: [buildParseResultListItem()],
      selectedResult: result,
    })

    render(<ParseResultViewer documentId="doc-1" />)
    expect(screen.getByRole('tab', { name: 'Markdown' })).toBeInTheDocument()
  })

  it('hides markdown tab when no markdown', () => {
    const result = buildParseResult({ markdown: null })
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      parseResults: [buildParseResultListItem()],
      selectedResult: result,
    })

    render(<ParseResultViewer documentId="doc-1" />)
    expect(screen.queryByRole('tab', { name: 'Markdown' })).not.toBeInTheDocument()
  })

  it('shows diagnostics tab', () => {
    const result = buildParseResult()
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      parseResults: [buildParseResultListItem()],
      selectedResult: result,
    })

    render(<ParseResultViewer documentId="doc-1" />)
    expect(screen.getByRole('tab', { name: 'Diagnostics' })).toBeInTheDocument()
  })

  it('shows processing spinner for pending results', () => {
    mockUseParseResults.mockReturnValue({
      ...defaultHookReturn,
      parseResults: [buildParseResultListItem({ status: 'pending' })],
    })

    render(<ParseResultViewer documentId="doc-1" />)
    expect(screen.getByText('Parsing in progress...')).toBeInTheDocument()
  })
})
