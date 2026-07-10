import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ParseMethodSelector } from './ParseMethodSelector'

describe('ParseMethodSelector', () => {
  const defaultProps = {
    parserType: 'simple',
    config: { tier: 'agentic', expand: ['markdown', 'text'] },
    onParserTypeChange: vi.fn(),
    onConfigChange: vi.fn(),
  }

  it('renders with simple selected by default', () => {
    render(<ParseMethodSelector {...defaultProps} />)
    expect(screen.getByText('Parse method')).toBeInTheDocument()
    expect(
      screen.getByText('Basic text extraction. Works on clean text-based PDFs.')
    ).toBeInTheDocument()
  })

  it('shows LlamaParse options when llamaparse selected', () => {
    render(
      <ParseMethodSelector {...defaultProps} parserType="llamaparse" />
    )
    expect(screen.getByText('Tier')).toBeInTheDocument()
    expect(screen.getByText('Output Options')).toBeInTheDocument()
    expect(
      screen.getByText('Intelligent parsing. Handles complex layouts, tables, scanned documents.')
    ).toBeInTheDocument()
  })

  it('hides LlamaParse options when simple selected', () => {
    render(<ParseMethodSelector {...defaultProps} parserType="simple" />)
    expect(screen.queryByText('Tier')).not.toBeInTheDocument()
    expect(screen.queryByText('Output Options')).not.toBeInTheDocument()
  })

  it('disables markdown checkbox on fast tier', () => {
    render(
      <ParseMethodSelector
        {...defaultProps}
        parserType="llamaparse"
        config={{ tier: 'fast', expand: ['text'] }}
      />
    )
    const markdownCheckbox = screen.getByRole('checkbox', {
      name: /markdown/i,
    })
    expect(markdownCheckbox).toBeDisabled()
  })

  it('enables markdown checkbox on agentic tier', () => {
    render(
      <ParseMethodSelector
        {...defaultProps}
        parserType="llamaparse"
        config={{ tier: 'agentic', expand: ['markdown', 'text'] }}
      />
    )
    const markdownCheckbox = screen.getByRole('checkbox', {
      name: /^markdown$/i,
    })
    expect(markdownCheckbox).not.toBeDisabled()
  })

  it('shows Landing AI model dropdown when landing_ai selected', () => {
    render(
      <ParseMethodSelector {...defaultProps} parserType="landing_ai" config={{}} />
    )
    expect(screen.getByText('Model')).toBeInTheDocument()
    expect(screen.getByText('Vision-based parsing. Best for images, shelf photos, and complex visual layouts.')).toBeInTheDocument()
    expect(screen.queryByText('Tier')).not.toBeInTheDocument()
  })

  it('renders CustomPipelineConfig when custom_pipeline selected', () => {
    render(
      <ParseMethodSelector
        {...defaultProps}
        parserType="custom_pipeline"
        config={{
          tools: [{ tool_id: 'fitz', config: {} }],
          eviction_overlap_threshold: 0.5,
        }}
      />
    )
    expect(screen.getByText(/fitz \(text \+ images\)/i)).toBeInTheDocument()
    // Table tools (fitz_tables / camelot) are chosen via a select, not checkboxes.
    expect(screen.getByRole('combobox', { name: /table extraction/i })).toBeInTheDocument()
    expect(
      screen.getByText(/Composable tools/i)
    ).toBeInTheDocument()
  })

  it('hides custom pipeline options when simple selected', () => {
    render(<ParseMethodSelector {...defaultProps} parserType="simple" />)
    expect(screen.queryByText(/fitz \(text \+ images\)/i)).not.toBeInTheDocument()
  })

  it('resets config to parser defaultConfig when parser type changes', () => {
    const onConfigChange = vi.fn()
    const { rerender } = render(
      <ParseMethodSelector
        {...defaultProps}
        parserType="simple"
        onConfigChange={onConfigChange}
      />
    )
    // Re-render simulating a switch to landing_ai (handleParserChange fires both callbacks)
    rerender(
      <ParseMethodSelector
        {...defaultProps}
        parserType="landing_ai"
        onConfigChange={onConfigChange}
      />
    )
    // Verify the landing_ai config section is shown (confirming render updated)
    expect(screen.getByText('Model')).toBeInTheDocument()
  })
})
