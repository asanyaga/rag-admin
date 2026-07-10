import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CustomPipelineConfig, normalizeCustomPipelineConfig } from './CustomPipelineConfig'

const fitzOnly = {
  tools: {
    fitz: {
      tool: 'fitz',
      config: { include_images: true, span_detail: false, min_chars_threshold: 10 },
    },
  },
  capabilities: { text_extraction: 'fitz' },
  eviction_overlap_threshold: 0.5,
}

const withFitzTables = {
  ...fitzOnly,
  tools: {
    ...fitzOnly.tools,
    fitz_tables: {
      tool: 'fitz_tables',
      config: { vertical_strategy: 'lines_strict', horizontal_strategy: 'lines_strict' },
    },
  },
  capabilities: { text_extraction: 'fitz', table_detection: 'fitz_tables' },
}

const withCamelot = {
  ...fitzOnly,
  tools: {
    ...fitzOnly.tools,
    camelot: { tool: 'camelot', config: { flavor: 'lattice', edge_tol: 50, row_tol: 2 } },
  },
  capabilities: { text_extraction: 'fitz', table_detection: 'camelot' },
}

describe('CustomPipelineConfig', () => {
  it('renders text extraction as a slot, not an always-on label', () => {
    render(<CustomPipelineConfig config={fitzOnly} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox', { name: /text extraction/i })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /table extraction/i })).toBeInTheDocument()
    expect(screen.queryByText(/always on/i)).not.toBeInTheDocument()
  })

  it('selecting fitz_tables adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    expect(next.capabilities.text_extraction).toBe('fitz')
    expect(next.capabilities.table_detection).toBe('fitz_tables')
    expect(next.tools.fitz_tables.tool).toBe('fitz_tables')
    expect(next.tools.camelot).toBeUndefined()
  })

  it('selecting camelot adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/^camelot/i))
    const next = onChange.mock.calls[0][0]
    expect(next.capabilities.table_detection).toBe('camelot')
    expect(next.tools.camelot.tool).toBe('camelot')
    expect(next.tools.fitz_tables).toBeUndefined()
  })

  it('selecting none removes existing table tool', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={withFitzTables} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByRole('option', { name: /none/i }))
    const next = onChange.mock.calls[0][0]
    expect(next.capabilities.table_detection).toBeUndefined()
    expect(next.tools.fitz_tables).toBeUndefined()
    expect(next.tools.camelot).toBeUndefined()
  })

  it('switching from camelot to fitz_tables removes camelot', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={withCamelot} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    expect(next.capabilities.table_detection).toBe('fitz_tables')
    expect(next.tools.fitz_tables).toBeDefined()
    expect(next.tools.camelot).toBeUndefined()
  })

  it('shows fitz_tables config panel when fitz_tables is selected', () => {
    render(<CustomPipelineConfig config={withFitzTables} onChange={vi.fn()} />)
    expect(screen.getAllByText(/vertical strategy/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/snap tolerance/i).length).toBeGreaterThan(0)
  })

  it('shows camelot flavor select when camelot is selected', () => {
    render(<CustomPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.getByText('Flavor')).toBeInTheDocument()
  })

  it('hides edge_tol/row_tol for camelot lattice flavor', () => {
    render(<CustomPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.queryByText('edge_tol')).not.toBeInTheDocument()
    expect(screen.queryByText('row_tol')).not.toBeInTheDocument()
  })

  it('shows edge_tol/row_tol for camelot stream flavor', () => {
    const withStream = {
      ...fitzOnly,
      tools: {
        ...fitzOnly.tools,
        camelot: { tool: 'camelot', config: { flavor: 'stream', edge_tol: 50, row_tol: 2 } },
      },
      capabilities: { text_extraction: 'fitz', table_detection: 'camelot' },
    }
    render(<CustomPipelineConfig config={withStream} onChange={vi.fn()} />)
    expect(screen.getByText('edge_tol')).toBeInTheDocument()
    expect(screen.getByText('row_tol')).toBeInTheDocument()
  })

})

describe('normalizeCustomPipelineConfig', () => {
  const OLD_ARRAY = {
    tools: [
      { tool_id: 'fitz', config: { min_chars_threshold: 10, include_images: true } },
    ],
    eviction_overlap_threshold: 0.5,
  }

  it('converts the old array shape to capability slots', () => {
    const n = normalizeCustomPipelineConfig(OLD_ARRAY)
    expect(Array.isArray(n.tools)).toBe(false)
    expect(n.tools['0']).toBeUndefined()          // no array-index key
    expect(n.tools.fitz.tool).toBe('fitz')
    expect(n.tools.fitz.config.include_images).toBe(true)
    expect(n.capabilities.text_extraction).toBe('fitz')
  })

  it('infers table_detection from an old array with a table tool', () => {
    const n = normalizeCustomPipelineConfig({
      tools: [
        { tool_id: 'fitz', config: {} },
        { tool_id: 'camelot', config: { flavor: 'stream' } },
      ],
    })
    expect(n.capabilities.text_extraction).toBe('fitz')
    expect(n.capabilities.table_detection).toBe('camelot')
    expect(n.tools.camelot.config.flavor).toBe('stream')
  })

  it('guarantees a text_extraction slot even if the input lacks one', () => {
    const n = normalizeCustomPipelineConfig({
      tools: { fitz_tables: { tool: 'fitz_tables', config: {} } },
      capabilities: { table_detection: 'fitz_tables' },
    })
    expect(n.capabilities.text_extraction).toBe('fitz')
    expect(n.tools.fitz.tool).toBe('fitz')
  })

  it('is idempotent on an already-normalized config', () => {
    const once = normalizeCustomPipelineConfig(OLD_ARRAY)
    const twice = normalizeCustomPipelineConfig(once)
    expect(twice).toEqual(once)
  })
})

describe('CustomPipelineConfig with a legacy config', () => {
  const OLD_ARRAY = {
    tools: [{ tool_id: 'fitz', config: { include_images: true, span_detail: false } }],
    eviction_overlap_threshold: 0.5,
  }

  it('emits a normalized capability-slot config on mount', () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={OLD_ARRAY} onChange={onChange} />)
    expect(onChange).toHaveBeenCalled()
    const next = onChange.mock.calls[0][0]
    expect(next.capabilities.text_extraction).toBe('fitz')
    expect(next.tools['0']).toBeUndefined()
    expect(Array.isArray(next.tools)).toBe(false)
  })

  it('never produces a config missing text_extraction after editing the table slot', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={OLD_ARRAY} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const calls = onChange.mock.calls
    const next = calls[calls.length - 1][0]
    expect(next.capabilities.text_extraction).toBe('fitz')
    expect(next.capabilities.table_detection).toBe('fitz_tables')
    expect(next.tools['0']).toBeUndefined()
  })
})
