import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TableGridEditor } from './TableGridEditor'
import { emptyModel } from './tableGrid'

describe('TableGridEditor', () => {
  it('edits cell text through onChange', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 1)} onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hello' } })
    expect(onChange).toHaveBeenCalled()
    const next = onChange.mock.calls.at(-1)![0]
    expect(next.cells[0].text).toBe('hello')
  })

  it('adds a row via the toolbar', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 1)} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add row/i }))
    expect(onChange.mock.calls.at(-1)![0].rows).toBe(2)
  })
})
