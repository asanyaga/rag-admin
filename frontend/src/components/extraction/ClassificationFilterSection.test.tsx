import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ClassificationFilterSection } from './ClassificationFilterSection'
import type { ClassificationFilterState } from '@/hooks/useClassificationFilter'

function baseState(o: Partial<ClassificationFilterState>): ClassificationFilterState {
  return {
    mode: 'select', eligibleRun: { id: 'r1' } as never, selectCategories: ['fin', 'legal'],
    selectedCategories: [], granularity: 'page',
    setSelectedCategories: vi.fn(), setGranularity: vi.fn(), ...o,
  }
}

const cfgProps = {
  classifyConfig: { labels: ['a', 'b'], classifierType: 'llm' },
  onClassifyConfigChange: vi.fn(),
  promptConfig: { provider: 'openai', model: 'gpt', temperature: 0, maxTokens: 10 } as never,
  onPromptConfigChange: vi.fn(),
}

describe('ClassificationFilterSection', () => {
  it('select mode: renders a checkbox per eligible category', () => {
    render(<ClassificationFilterSection state={baseState({})} {...cfgProps} />)
    expect(screen.getByLabelText('fin')).toBeInTheDocument()
    expect(screen.getByLabelText('legal')).toBeInTheDocument()
  })

  it('select mode: toggles category', () => {
    const setSel = vi.fn()
    render(<ClassificationFilterSection state={baseState({ setSelectedCategories: setSel })} {...cfgProps} />)
    fireEvent.click(screen.getByLabelText('fin'))
    expect(setSel).toHaveBeenCalledWith(['fin'])
  })

  it('configure mode: renders label editor and filter-subset over classify labels', () => {
    render(<ClassificationFilterSection
      state={baseState({ mode: 'configure', eligibleRun: null, selectCategories: [] })} {...cfgProps} />)
    expect(screen.getByText(/Labels to classify/i)).toBeInTheDocument()
    expect(screen.getByLabelText('a')).toBeInTheDocument()
    expect(screen.getByLabelText('b')).toBeInTheDocument()
  })
})
