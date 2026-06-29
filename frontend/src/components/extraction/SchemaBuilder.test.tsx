import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SchemaBuilder } from './SchemaBuilder'

const emptySchema = { type: 'object', properties: {} }

describe('SchemaBuilder', () => {
  it('renders builder tab and Add field button by default', () => {
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    expect(screen.getByRole('tab', { name: /builder/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add field/i })).toBeInTheDocument()
  })

  it('switches to JSON view on tab click', async () => {
    const user = userEvent.setup()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('calls onChange when a field is added', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ type: 'object' }))
  })

  it('renders existing fields from value prop', () => {
    const schema = {
      type: 'object',
      properties: { invoice_number: { type: 'string', description: 'Invoice #' } },
    }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('invoice_number')).toBeInTheDocument()
  })

  it('JSON view shows serialized schema', async () => {
    const user = userEvent.setup()
    const schema = { type: 'object', properties: { x: { type: 'string' } } }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveValue(JSON.stringify(schema, null, 2))
  })

  it('shows parse error on invalid JSON', async () => {
    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)
    await user.type(textarea, '{bad json')
    act(() => { vi.advanceTimersByTime(400) })
    expect(screen.getByText(/invalid json/i)).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('preserves builder fields when JSON becomes invalid', async () => {
    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    const schema = { type: 'object', properties: { name: { type: 'string', description: 'Full name' } } }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)
    await user.type(textarea, 'not valid json')
    act(() => { vi.advanceTimersByTime(400) })
    await user.click(screen.getByRole('tab', { name: /builder/i }))
    expect(screen.getByDisplayValue('name')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('calls onValidChange(false) when a blank field is added', async () => {
    const user = userEvent.setup()
    const onValidChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} onValidChange={onValidChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    expect(onValidChange).toHaveBeenLastCalledWith(false)
  })

  it('calls onValidChange(true) when all fields have keys', async () => {
    const user = userEvent.setup()
    const onValidChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} onValidChange={onValidChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    const keyInput = screen.getByPlaceholderText('field_name')
    await user.type(keyInput, 'my_field')
    expect(onValidChange).toHaveBeenLastCalledWith(true)
  })
})
