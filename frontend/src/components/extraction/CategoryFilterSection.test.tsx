import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CategoryFilterSection } from './CategoryFilterSection'
import type { CategoryFilterState } from '@/hooks/useCategoryFilter'

function state(overrides: Partial<CategoryFilterState>): CategoryFilterState {
  return {
    eligibleRun: { id: 'r1' } as never,
    availableCategories: ['fin', 'legal'],
    selectedCategories: [],
    granularity: 'page',
    setSelectedCategories: vi.fn(),
    setGranularity: vi.fn(),
    toPreprocessStage: () => null,
    ...overrides,
  }
}

describe('CategoryFilterSection', () => {
  it('renders a checkbox per available category', () => {
    render(<CategoryFilterSection state={state({})} />)
    expect(screen.getByText('fin')).toBeInTheDocument()
    expect(screen.getByText('legal')).toBeInTheDocument()
  })

  it('shows blank state when no eligible run', () => {
    render(<CategoryFilterSection state={state({ eligibleRun: null, availableCategories: [] })} />)
    expect(screen.getByText(/no completed classification/i)).toBeInTheDocument()
  })

  it('toggles a category selection', () => {
    const setSelected = vi.fn()
    render(<CategoryFilterSection state={state({ setSelectedCategories: setSelected })} />)
    fireEvent.click(screen.getByLabelText('fin'))
    expect(setSelected).toHaveBeenCalledWith(['fin'])
  })
})
