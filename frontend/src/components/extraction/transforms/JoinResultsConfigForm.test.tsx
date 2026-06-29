import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { JoinResultsConfigForm } from './JoinResultsConfigForm'
import type { JoinResultsConfig } from '@/types/resultTransform'
import type { ExtractionResultListItem } from '@/types/extraction'

const DEFAULT: JoinResultsConfig = { joinKey: '', joinType: 'left', lookupResultIds: [] }

const AVAILABLE: ExtractionResultListItem[] = [
  {
    id: 'r2', documentId: 'doc1', extractionSchemaId: 'schema1',
    extractionMethod: 'llm', status: 'completed', statusMessage: null,
    timeoutMinutes: null, createdAt: '2024-01-01',
  },
  {
    id: 'r3', documentId: 'doc1', extractionSchemaId: 'schema2',
    extractionMethod: 'llm', status: 'completed', statusMessage: null,
    timeoutMinutes: null, createdAt: '2024-01-01',
  },
]

describe('JoinResultsConfigForm', () => {
  it('renders join key input', () => {
    render(<JoinResultsConfigForm value={DEFAULT} onChange={() => {}} primaryResultId="r1" availableResults={AVAILABLE} />)
    expect(screen.getByPlaceholderText(/e\.g\. series/i)).toBeInTheDocument()
  })

  it('calls onChange when joinKey is edited', () => {
    const onChange = vi.fn()
    render(<JoinResultsConfigForm value={DEFAULT} onChange={onChange} primaryResultId="r1" availableResults={AVAILABLE} />)
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. series/i), { target: { value: 'series' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ joinKey: 'series' }))
  })

  it('shows primary result label as non-interactive', () => {
    render(<JoinResultsConfigForm value={DEFAULT} onChange={() => {}} primaryResultId="r1" availableResults={AVAILABLE} />)
    expect(screen.getByText(/primary/i)).toBeInTheDocument()
  })

  it('adds the first unselected lookup result when Add lookup is clicked', () => {
    const onChange = vi.fn()
    render(
      <JoinResultsConfigForm
        value={DEFAULT}
        onChange={onChange}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /add lookup/i }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ lookupResultIds: ['r2'] })
    )
  })

  it('removes a lookup result', () => {
    const onChange = vi.fn()
    const value: JoinResultsConfig = { joinKey: 'series', joinType: 'left', lookupResultIds: ['r2'] }
    render(
      <JoinResultsConfigForm
        value={value}
        onChange={onChange}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    fireEvent.click(screen.getByTitle(/remove lookup/i))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ lookupResultIds: [] }))
  })

  it('changing to inner join type calls onChange with updated joinType', () => {
    const onChange = vi.fn()
    render(<JoinResultsConfigForm value={DEFAULT} onChange={onChange} primaryResultId="r1" availableResults={AVAILABLE} />)
    fireEvent.click(screen.getByRole('button', { name: /inner/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ joinType: 'inner' }))
  })

  it('hides Add lookup when all available results are already selected', () => {
    const value: JoinResultsConfig = { joinKey: '', joinType: 'left', lookupResultIds: ['r2', 'r3'] }
    render(
      <JoinResultsConfigForm
        value={value}
        onChange={() => {}}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    expect(screen.queryByRole('button', { name: /add lookup/i })).not.toBeInTheDocument()
  })

  it('hides Add lookup when 4 lookup results are already selected (max 5 total)', () => {
    const value: JoinResultsConfig = {
      joinKey: '', joinType: 'left',
      lookupResultIds: ['r2', 'r3', 'r4', 'r5'],
    }
    const manyAvailable = [...AVAILABLE,
      { id: 'r4', documentId: 'doc1', extractionSchemaId: 's3', extractionMethod: 'llm', status: 'completed' as const, statusMessage: null, timeoutMinutes: null, createdAt: '2024-01-01' },
      { id: 'r5', documentId: 'doc1', extractionSchemaId: 's4', extractionMethod: 'llm', status: 'completed' as const, statusMessage: null, timeoutMinutes: null, createdAt: '2024-01-01' },
      { id: 'r6', documentId: 'doc1', extractionSchemaId: 's5', extractionMethod: 'llm', status: 'completed' as const, statusMessage: null, timeoutMinutes: null, createdAt: '2024-01-01' },
    ]
    render(
      <JoinResultsConfigForm
        value={value}
        onChange={() => {}}
        primaryResultId="r1"
        availableResults={manyAvailable}
      />
    )
    expect(screen.queryByRole('button', { name: /add lookup/i })).not.toBeInTheDocument()
  })
})
