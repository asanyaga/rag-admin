import { render, screen, fireEvent } from '@testing-library/react'
import { QueryList } from './QueryList'
import type { GoldenSetQuery } from '@/types/golden-set'

const makeQuery = (id: string, text: string, sourceMethod = 'manual' as const): GoldenSetQuery => ({
  id,
  queryText: text,
  sourceMethod,
  reviewStatus: 'accepted',
  reasoning: null,
  questionType: null,
  referenceAnswer: null,
  sources: [],
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
})

const queries = [
  makeQuery('1', 'What is the revenue for Q3?'),
  makeQuery('2', 'How does the refund policy work?', 'auto_generated'),
  makeQuery('3', 'Describe the onboarding process.', 'imported'),
]

test('renders full query text without truncation', () => {
  render(
    <QueryList
      queries={queries}
      selectedId={null}
      onSelect={vi.fn()}
      onAdd={vi.fn()}
    />
  )
  expect(screen.getByText('What is the revenue for Q3?')).toBeInTheDocument()
})

test('search filters the list', () => {
  render(
    <QueryList
      queries={queries}
      selectedId={null}
      onSelect={vi.fn()}
      onAdd={vi.fn()}
    />
  )
  const search = screen.getByPlaceholderText('Search queries…')
  fireEvent.change(search, { target: { value: 'refund' } })
  expect(screen.getByText('How does the refund policy work?')).toBeInTheDocument()
  expect(screen.queryByText('What is the revenue for Q3?')).not.toBeInTheDocument()
})

test('source method filter narrows list', () => {
  render(
    <QueryList
      queries={queries}
      selectedId={null}
      onSelect={vi.fn()}
      onAdd={vi.fn()}
    />
  )
  fireEvent.click(screen.getByRole('button', { name: /auto/i }))
  expect(screen.getByText('How does the refund policy work?')).toBeInTheDocument()
  expect(screen.queryByText('What is the revenue for Q3?')).not.toBeInTheDocument()
})
