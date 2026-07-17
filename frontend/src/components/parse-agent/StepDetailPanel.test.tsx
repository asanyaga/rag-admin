import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { StepDetailPanel } from './StepDetailPanel'
import type { ParseAgentRunStep } from '@/types/parseAgent'

function step(over: Partial<ParseAgentRunStep> = {}): ParseAgentRunStep {
  return {
    id: 'step-1',
    seq: 0,
    node: 'parse',
    phase: 'end',
    status: 'succeeded',
    inputKeys: ['file_path'],
    outputKeys: ['parse_run_id'],
    stateDelta: {},
    message: null,
    durationMs: 4200,
    createdAt: '2026-07-17T10:00:00Z',
    ...over,
  }
}

describe('StepDetailPanel', () => {
  it('renders a link to the results viewer when stateDelta.parse_run_id is a string', () => {
    render(
      <MemoryRouter>
        <StepDetailPanel step={step({ stateDelta: { parse_run_id: 'pr-1' } })} />
      </MemoryRouter>
    )
    const link = screen.getByRole('link', { name: /open parsed document/i })
    expect(link.getAttribute('href')).toBe('/parse-runs/pr-1')
  })

  it('renders no link when parse_run_id is absent', () => {
    render(
      <MemoryRouter>
        <StepDetailPanel step={step({ stateDelta: {} })} />
      </MemoryRouter>
    )
    expect(
      screen.queryByRole('link', { name: /open parsed document/i })
    ).not.toBeInTheDocument()
  })

  it('renders the empty-state text when step is null', () => {
    render(
      <MemoryRouter>
        <StepDetailPanel step={null} />
      </MemoryRouter>
    )
    expect(
      screen.getByText(/select a step to inspect/i)
    ).toBeInTheDocument()
  })
})
