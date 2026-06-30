import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RunTimeline } from './RunTimeline'
import type { ParseRunListItem } from '@/types/cdm'

vi.mock('@/api/parseRuns', () => ({
  deleteParseRun: vi.fn(),
}))

const run = (over: Partial<ParseRunListItem> = {}): ParseRunListItem => ({
  id: 'r1',
  sourceDocumentId: 's1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: null,
  outputTokens: null,
  cost: {},
  warnings: [],
  failedPages: [],
  providerRefs: {},
  error: null,
  config: {},
  createdAt: '2026-04-25T10:00:00Z',
  ...over,
})

describe('RunTimeline', () => {
  it('renders an empty state', () => {
    render(
      <MemoryRouter>
        <RunTimeline documentId="d1" runs={[]} />
      </MemoryRouter>
    )
    expect(screen.getByText(/no parse runs/i)).toBeInTheDocument()
  })

  it('renders a row per run with an Open viewer link', () => {
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'r1' }), run({ id: 'r2', status: 'failed' })]}
        />
      </MemoryRouter>
    )
    const links = screen.getAllByRole('link', { name: /open viewer/i })
    expect(links).toHaveLength(2)
    expect(links[0].getAttribute('href')).toBe('/parse/d1/runs/r1')
  })

  it('renders a delete button per run row', () => {
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'r1' }), run({ id: 'r2' })]}
          onRunDeleted={vi.fn()}
        />
      </MemoryRouter>
    )
    expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(2)
  })
})
