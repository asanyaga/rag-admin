import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RunTimeline } from './RunTimeline'
import type { ParseRunListItem } from '@/types/cdm'

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
        <RunTimeline documentId="d1" runs={[]} onReparse={vi.fn()} />
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
          onReparse={vi.fn()}
        />
      </MemoryRouter>
    )
    const links = screen.getAllByRole('link', { name: /open viewer/i })
    expect(links).toHaveLength(2)
    expect(links[0].getAttribute('href')).toBe('/documents/d1/runs/r1')
  })

  it('shows Re-parse only on the latest row and triggers handler', async () => {
    const onReparse = vi.fn()
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'newest' }), run({ id: 'older' })]}
          onReparse={onReparse}
        />
      </MemoryRouter>
    )
    const reparseButtons = screen.getAllByRole('button', { name: /re-parse/i })
    expect(reparseButtons).toHaveLength(1)
    await userEvent.click(reparseButtons[0])
    expect(onReparse).toHaveBeenCalled()
  })
})
