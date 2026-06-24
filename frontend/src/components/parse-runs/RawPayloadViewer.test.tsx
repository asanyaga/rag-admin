import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RawPayloadViewer } from './RawPayloadViewer'

describe('RawPayloadViewer', () => {
  it('renders an empty state when payload is null', () => {
    render(<RawPayloadViewer payload={null} />)
    expect(
      screen.getByText(/no raw payload was captured/i)
    ).toBeInTheDocument()
  })

  it('renders a loading state', () => {
    render(<RawPayloadViewer payload={undefined} isLoading />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders an error state', () => {
    render(
      <RawPayloadViewer
        payload={undefined}
        isLoading={false}
        error="boom"
      />
    )
    expect(screen.getByText(/boom/i)).toBeInTheDocument()
  })

  it('renders payload keys when given a dict', () => {
    render(
      <RawPayloadViewer
        payload={{ job_metadata: { job_id: 'j1' }, pages: [] }}
      />
    )
    expect(screen.getByText(/job_metadata/)).toBeInTheDocument()
    expect(screen.getByText(/pages/)).toBeInTheDocument()
  })

  it('copies JSON to clipboard on Copy click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    render(<RawPayloadViewer payload={{ a: 1 }} />)
    await userEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(writeText).toHaveBeenCalledWith(
      JSON.stringify({ a: 1 }, null, 2)
    )
  })
})
