import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ParseConfigFamilySelector } from './ParseConfigFamilySelector'
import type { ParseConfigOption } from '@/lib/parsed-documents'

const llamaOption: ParseConfigOption = {
  parser: 'llamaparse',
  parseConfigHash: 'abc123',
  config: { result_type: 'markdown', num_workers: 4 },
  parsedDocumentCount: 3,
  hasFullMarkdown: true,
  latestParsedAt: '2026-04-30T09:11:00Z',
}

const landingOption: ParseConfigOption = {
  parser: 'landingai',
  parseConfigHash: 'def456',
  config: { model: 'default' },
  parsedDocumentCount: 1,
  hasFullMarkdown: false,
  latestParsedAt: '2026-04-29T14:32:00Z',
}

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('ParseConfigFamilySelector', () => {
  it('renders parser names and document counts', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('LlamaParse')).toBeInTheDocument()
    expect(screen.getByText('LandingAI')).toBeInTheDocument()
    expect(screen.getByText('3 parsed documents')).toBeInTheDocument()
    expect(screen.getByText('1 parsed document')).toBeInTheDocument()
  })

  it('shows markdown badge when hasFullMarkdown is true', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('markdown')).toBeInTheDocument()
  })

  it('does not show markdown badge when hasFullMarkdown is false', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[landingOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByText('markdown')).not.toBeInTheDocument()
  })

  it('calls onChange with parser and parseConfigHash when an option is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={null}
        onChange={onChange}
      />,
    )
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    expect(onChange).toHaveBeenCalledWith({
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
    })
  })

  it('renders the empty state when no options are provided', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/no parse runs found/i)).toBeInTheDocument()
  })

  it('marks the selected option with aria-pressed', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={{ parser: 'llamaparse', parseConfigHash: 'abc123' }}
        onChange={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: /llamaparse/i }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: /landingai/i }),
    ).toHaveAttribute('aria-pressed', 'false')
  })
})
