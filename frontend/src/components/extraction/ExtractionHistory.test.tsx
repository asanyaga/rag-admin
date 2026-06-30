import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { ExtractionHistory } from './ExtractionHistory'
import type { ExtractionResultListItem, ExtractionSchema } from '@/types/extraction'

const results: ExtractionResultListItem[] = [
  {
    id: 'r1',
    documentId: 'd1',
    extractionSchemaId: 's1',
    extractionMethod: 'llm',
    status: 'completed',
    statusMessage: null,
    timeoutMinutes: null,
    createdAt: '2026-01-01T00:00:00Z',
  },
]

const schemas: ExtractionSchema[] = [
  {
    id: 's1',
    projectId: 'p1',
    name: 'Invoice Schema',
    description: null,
    schemaDefinition: {},
    extractionTarget: 'PER_DOC',
    createdBy: 'u1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  },
]

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('ExtractionHistory', () => {
  it('renders result rows as links to /extract/:id', () => {
    wrap(
      <ExtractionHistory
        results={results}
        isLoading={false}
        schemas={schemas}
        onDeleteResult={vi.fn()}
        onExportResult={vi.fn()}
      />,
    )
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/extract/r1')
  })

  it('shows schema name on the row', () => {
    wrap(
      <ExtractionHistory
        results={results}
        isLoading={false}
        schemas={schemas}
        onDeleteResult={vi.fn()}
        onExportResult={vi.fn()}
      />,
    )
    expect(screen.getByText('Invoice Schema')).toBeInTheDocument()
  })

  it('calls onDeleteResult without navigating when delete clicked', async () => {
    const onDeleteResult = vi.fn().mockResolvedValue(undefined)
    wrap(
      <ExtractionHistory
        results={results}
        isLoading={false}
        schemas={schemas}
        onDeleteResult={onDeleteResult}
        onExportResult={vi.fn()}
      />,
    )
    const deleteBtn = screen.getByRole('button', { name: /delete extraction run/i })
    await userEvent.click(deleteBtn)
    expect(onDeleteResult).toHaveBeenCalledWith('r1')
  })

  it('shows empty state when no results', () => {
    wrap(
      <ExtractionHistory
        results={[]}
        isLoading={false}
        schemas={[]}
        onDeleteResult={vi.fn()}
        onExportResult={vi.fn()}
      />,
    )
    expect(screen.getByText(/no extractions yet/i)).toBeInTheDocument()
  })
})
