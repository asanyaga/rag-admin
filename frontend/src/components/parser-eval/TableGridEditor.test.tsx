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
    const next = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(next.cells[0].text).toBe('hello')
  })

  it('adds a row via the toolbar', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 1)} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add row/i }))
    expect(onChange.mock.calls[onChange.mock.calls.length - 1][0].rows).toBe(2)
  })

  it('highlights the anchor cell on mousedown', () => {
    render(<TableGridEditor model={emptyModel(1, 2)} onChange={vi.fn()} />)
    const cell = screen.getByLabelText('cell 0,0').closest('td')!
    fireEvent.mouseDown(cell)
    expect(cell.className).toContain('ring-primary')
  })

  it('drag-selects a range and merges it', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 2)} onChange={onChange} />)
    fireEvent.mouseDown(screen.getByLabelText('cell 0,0').closest('td')!)
    fireEvent.mouseEnter(screen.getByLabelText('cell 0,1').closest('td')!)
    fireEvent.click(screen.getByRole('button', { name: /merge/i }))
    const next = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(next.cells.find((c: { row: number; col: number }) => c.row === 0 && c.col === 0).colspan)
      .toBe(2)
  })
})
