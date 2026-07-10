import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CustomPipelineConfig } from './CustomPipelineConfig'

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
