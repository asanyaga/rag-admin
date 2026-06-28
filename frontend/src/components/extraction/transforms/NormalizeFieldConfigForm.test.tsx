import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NormalizeFieldConfigForm } from './NormalizeFieldConfigForm'
import type { NormalizeFieldConfig } from '@/types/resultTransform'

const DEFAULT: NormalizeFieldConfig = { fields: [{ sourceField: '', outputField: '', rules: [] }] }

describe('NormalizeFieldConfigForm', () => {
  it('renders source field and output field inputs for first entry', () => {
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={() => {}} />)
    expect(screen.getByPlaceholderText(/modelName/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/baseModel/i)).toBeInTheDocument()
  })

  it('calls onChange when sourceField is edited', () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText(/modelName/i), { target: { value: 'myField' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: expect.arrayContaining([expect.objectContaining({ sourceField: 'myField' })]),
      }),
    )
  })

  it('Add field button appends a new field entry', () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add field/i }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ fields: expect.arrayContaining([expect.any(Object), expect.any(Object)]) }),
    )
  })

  it('Add rule button on an entry appends a rule to that entry', () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add rule/i }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: [expect.objectContaining({ rules: [expect.objectContaining({ type: 'trim' })] })],
      }),
    )
  })

  it('renders multiple field entries with their own comboboxes', () => {
    const value: NormalizeFieldConfig = {
      fields: [
        { sourceField: 'a', outputField: 'a_out', rules: [{ type: 'trim' }, { type: 'lowercase' }] },
        { sourceField: 'b', outputField: 'b_out', rules: [{ type: 'uppercase' }] },
      ],
    }
    render(<NormalizeFieldConfigForm value={value} onChange={() => {}} />)
    expect(screen.getAllByRole('combobox')).toHaveLength(3)
  })

  it('remove field button is hidden when only one entry exists', () => {
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={() => {}} />)
    expect(screen.queryByTitle('Remove field')).not.toBeInTheDocument()
  })

  it('remove field button is visible when multiple entries exist', () => {
    const value: NormalizeFieldConfig = {
      fields: [
        { sourceField: 'a', outputField: 'a_out', rules: [] },
        { sourceField: 'b', outputField: 'b_out', rules: [] },
      ],
    }
    render(<NormalizeFieldConfigForm value={value} onChange={() => {}} />)
    expect(screen.getAllByTitle('Remove field')).toHaveLength(2)
  })
})
