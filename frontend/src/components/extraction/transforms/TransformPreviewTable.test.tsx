import { it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TransformPreviewTable } from './TransformPreviewTable'

it('renders a flag chip for a flagged row', () => {
  render(<TransformPreviewTable
    rows={[{ sku: 'X', modelName: 'GP-40' }]}
    flags={[{ rowIndex: 0, flag: 'no_specs' }]} />)
  expect(screen.getByText('no_specs')).toBeInTheDocument()
})
