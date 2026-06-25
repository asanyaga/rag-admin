import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunHeader } from './RunHeader'
import type { ParseRunListItem } from '@/types/cdm'

const baseRun: ParseRunListItem = {
  id: 'run-1',
  sourceDocumentId: 'src-1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: 100,
  outputTokens: 200,
  cost: { total: 0.012 },
  warnings: [],
  failedPages: [],
  providerRefs: { llamaparse_job_id: 'job-1' },
  error: null,
  config: { tier: 'agentic' },
  createdAt: '2026-04-25T10:00:00Z',
}

describe('RunHeader', () => {
  it('renders parser, status, and duration', () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText(/llamaparse/i)).toBeInTheDocument()
    expect(screen.getByText(/succeeded/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.2s|4200/)).toBeInTheDocument()
  })

  it('exposes config JSON when expanded', async () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /config/i }))
    expect(screen.getByText(/"tier": "agentic"/)).toBeInTheDocument()
  })

  it('triggers onReparse when the re-parse button is clicked', async () => {
    const onReparse = vi.fn()
    render(<RunHeader run={baseRun} onReparse={onReparse} onDelete={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /re-parse/i }))
    expect(onReparse).toHaveBeenCalled()
  })

  it('shows error text for failed runs', () => {
    render(
      <RunHeader
        run={{ ...baseRun, status: 'failed', error: 'sdk down' }}
        onReparse={vi.fn()}
        onDelete={vi.fn()}
      />
    )
    expect(screen.getByText(/sdk down/)).toBeInTheDocument()
  })

  it('triggers onDelete when the delete button is clicked', async () => {
    const onDelete = vi.fn()
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={onDelete} />)
    await userEvent.click(screen.getByRole('button', { name: /delete run/i }))
    expect(onDelete).toHaveBeenCalled()
  })
})
