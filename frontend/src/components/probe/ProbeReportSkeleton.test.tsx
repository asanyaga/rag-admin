import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ProbeReportSkeleton } from './ProbeReportSkeleton'

describe('ProbeReportSkeleton', () => {
  it('renders a placeholder report while a probe is in flight', () => {
    render(<ProbeReportSkeleton />)
    expect(screen.getByTestId('probe-report-skeleton')).toBeInTheDocument()
    expect(screen.getByText(/Probing document/i)).toBeInTheDocument()
  })
})
