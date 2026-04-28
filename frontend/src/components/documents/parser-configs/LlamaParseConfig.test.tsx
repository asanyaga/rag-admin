import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LlamaParseConfig } from './LlamaParseConfig'

const defaultConfig = { tier: 'agentic', expand: ['markdown', 'text', 'items'] }

describe('LlamaParseConfig', () => {
  it('renders tier select with current value', () => {
    render(<LlamaParseConfig config={defaultConfig} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders all three output checkboxes', () => {
    render(<LlamaParseConfig config={defaultConfig} onChange={vi.fn()} />)
    expect(screen.getByLabelText(/text \(always included\)/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/markdown/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/structured items/i)).toBeInTheDocument()
  })

  it('calls onChange with updated expand when markdown is unchecked', async () => {
    const onChange = vi.fn()
    render(<LlamaParseConfig config={defaultConfig} onChange={onChange} />)
    await userEvent.click(screen.getByLabelText(/markdown/i))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ expand: expect.not.arrayContaining(['markdown']) })
    )
  })

  it('disables markdown and items when fast tier is selected', async () => {
    const onChange = vi.fn()
    render(
      <LlamaParseConfig config={{ tier: 'fast', expand: ['text'] }} onChange={onChange} />
    )
    const markdownCheckbox = screen.getByLabelText(/markdown/i)
    expect(markdownCheckbox).toBeDisabled()
  })
})
