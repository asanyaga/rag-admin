import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LandingAIConfig } from './LandingAIConfig'

describe('LandingAIConfig', () => {
  it('renders model select', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders model label', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByText('Model')).toBeInTheDocument()
  })

  it('renders description text', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByText(/vision-based document parsing model/i)).toBeInTheDocument()
  })

  it('defaults to dpt-2-latest when model not set', () => {
    render(<LandingAIConfig config={{}} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('disables select when disabled prop is true', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} disabled />)
    expect(screen.getByRole('combobox')).toBeDisabled()
  })
})
