import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ClassificationConfig } from './ClassificationConfig'

describe('ClassificationConfig', () => {
  it('renders the labels input and Add button', () => {
    render(<ClassificationConfig onChange={() => {}} />)
    expect(screen.getByPlaceholderText('e.g. balance_sheet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
  })

  it('adds a label on Add button click and calls onChange', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'income_statement' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByText('income_statement')).toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ['income_statement'] }),
    )
  })

  it('adds a label on Enter keydown', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    const input = screen.getByPlaceholderText('e.g. balance_sheet')
    fireEvent.change(input, { target: { value: 'balance_sheet' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByText('balance_sheet')).toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ['balance_sheet'] }),
    )
  })

  it('removes a label when its remove button is clicked', () => {
    const onChange = vi.fn()
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['income_statement'] }}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('income_statement')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove income_statement' }))
    expect(screen.queryByText('income_statement')).not.toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labels: [] }))
  })

  it('does not add a duplicate label and does not call onChange', () => {
    const onChange = vi.fn()
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['income_statement'] }}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'income_statement' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('seeds labels from defaultValues', () => {
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['a', 'b'] }}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
  })

  it('shows Batch settings trigger when classifierType is llm (default)', () => {
    render(<ClassificationConfig onChange={() => {}} />)
    expect(screen.getByText('Batch settings')).toBeInTheDocument()
  })

  it('calls onChange with correct llm classifierConfig shape', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'test_label' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        classifierType: 'llm',
        classifierConfig: expect.objectContaining({
          provider: expect.any(String),
          model: expect.any(String),
          batch_size: expect.any(Number),
          batch_overlap: expect.any(Number),
          llm_config: expect.objectContaining({
            temperature: expect.any(Number),
            max_tokens: expect.any(Number),
          }),
        }),
      }),
    )
  })
})
