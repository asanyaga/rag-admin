import { render, screen } from '@testing-library/react'
import { QueryEditor } from './QueryEditor'
import type { GoldenSetQuery } from '@/types/golden-set'

const baseQuery: GoldenSetQuery = {
  id: 'q1',
  queryText: 'What is the refund policy?',
  sourceMethod: 'auto_generated',
  reviewStatus: 'accepted',
  reasoning: 'This tests the refund section.',
  questionType: 'factual',
  referenceAnswer: null,
  sources: [],
  createdAt: '2024-03-01T10:00:00Z',
  updatedAt: '2024-03-01T10:00:00Z',
}

test('shows origin label in metadata footer', () => {
  render(
    <QueryEditor
      query={baseQuery}
      projectId="proj1"
      onUpdateText={vi.fn()}
      onUpdateReferenceAnswer={vi.fn()}
      onDelete={vi.fn()}
      onAddSource={vi.fn()}
      onDeleteSource={vi.fn()}
    />
  )
  expect(screen.getByText('Auto-generated')).toBeInTheDocument()
})

test('shows reasoning when present', () => {
  render(
    <QueryEditor
      query={baseQuery}
      projectId="proj1"
      onUpdateText={vi.fn()}
      onUpdateReferenceAnswer={vi.fn()}
      onDelete={vi.fn()}
      onAddSource={vi.fn()}
      onDeleteSource={vi.fn()}
    />
  )
  expect(screen.getByText('This tests the refund section.')).toBeInTheDocument()
})

test('does not show reasoning section when reasoning is null', () => {
  render(
    <QueryEditor
      query={{ ...baseQuery, reasoning: null, sourceMethod: 'manual' }}
      projectId="proj1"
      onUpdateText={vi.fn()}
      onUpdateReferenceAnswer={vi.fn()}
      onDelete={vi.fn()}
      onAddSource={vi.fn()}
      onDeleteSource={vi.fn()}
    />
  )
  expect(screen.queryByText(/reasoning/i)).not.toBeInTheDocument()
})
