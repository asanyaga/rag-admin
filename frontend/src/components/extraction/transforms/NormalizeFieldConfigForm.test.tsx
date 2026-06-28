import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NormalizeFieldConfigForm } from './NormalizeFieldConfigForm'
import type { NormalizeFieldConfig } from '@/types/resultTransform'

const DEFAULT: NormalizeFieldConfig = { sourceField: '', outputField: '', rules: [] }

describe('NormalizeFieldConfigForm', () => {
  it('renders sourceField and outputField inputs', () => {
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={() => {}} />)
    expect(screen.getByLabelText(/source field/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/output field/i)).toBeInTheDocument()
  })

  it('calls onChange when sourceField is edited', () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText(/source field/i), { target: { value: 'modelName' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ sourceField: 'modelName' }))
  })

  it('renders Add rule button and adds a trim rule when clicked', async () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add rule/i }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ rules: [expect.objectContaining({ type: 'trim' })] }),
    )
  })

  it('renders existing rules as comboboxes', () => {
    const value: NormalizeFieldConfig = {
      sourceField: 'modelName',
      outputField: 'baseModel',
      rules: [{ type: 'trim' }, { type: 'lowercase' }],
    }
    render(<NormalizeFieldConfigForm value={value} onChange={() => {}} />)
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
  })
})
