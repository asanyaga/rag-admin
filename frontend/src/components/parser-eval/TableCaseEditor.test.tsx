import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TableCaseEditor } from './TableCaseEditor'

const oneTable = [{ page: 1, html: '<table><tr><td>a</td></tr></table>' }]

describe('TableCaseEditor', () => {
  it('adds a table on an existing page (stays same page)', async () => {
    const onSave = vi.fn()
    render(<TableCaseEditor tables={oneTable} onSave={onSave} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /add table on this page/i }))
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    const [arg] = onSave.mock.calls[onSave.mock.calls.length - 1]
    expect(arg).toHaveLength(2)
    expect((arg as { page: number }[]).every((t) => t.page === 1)).toBe(true)
  })

  it('adds a new page with its own table, serialized page-major', async () => {
    const onSave = vi.fn()
    render(<TableCaseEditor tables={oneTable} onSave={onSave} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /add page/i }))
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    const [arg] = onSave.mock.calls[onSave.mock.calls.length - 1]
    expect((arg as { page: number }[]).map((t) => t.page)).toEqual([1, 2])
  })
})
