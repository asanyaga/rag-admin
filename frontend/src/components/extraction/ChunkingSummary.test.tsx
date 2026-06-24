import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChunkingSummary } from './ChunkingSummary'

describe('ChunkingSummary', () => {
  it('renders chunk count and token usage when present', () => {
    render(<ChunkingSummary metadata={{ chunkCount: 3, usage: { total_tokens: 4210 } }} />)
    expect(screen.getByText(/3 chunks/i)).toBeInTheDocument()
    expect(screen.getByText(/4,210 tokens/i)).toBeInTheDocument()
  })

  it('renders a conflicts callout when scalarConflicts present', () => {
    render(
      <ChunkingSummary
        metadata={{ chunkCount: 2, scalarConflicts: [{ path: 'currency', kept: 'EUR', discarded: 'USD' }] }}
      />
    )
    expect(screen.getByText(/conflicting values/i)).toBeInTheDocument()
    expect(screen.getByText(/currency/)).toBeInTheDocument()
  })

  it('renders nothing when metadata lacks chunking fields', () => {
    const { container } = render(<ChunkingSummary metadata={{ model: 'x', usage: {} }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when metadata is null', () => {
    const { container } = render(<ChunkingSummary metadata={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
