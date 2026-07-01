import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LocalPipelineConfig } from './LocalPipelineConfig'

const fitzOnly = {
  tools: [
    {
      tool_id: 'fitz',
      config: { include_images: true, span_detail: false, min_chars_threshold: 10 },
    },
  ],
  eviction_overlap_threshold: 0.5,
}

const withFitzTables = {
  ...fitzOnly,
  tools: [
    ...fitzOnly.tools,
    {
      tool_id: 'fitz_tables',
      config: { vertical_strategy: 'lines_strict', horizontal_strategy: 'lines_strict' },
    },
  ],
}

const withCamelot = {
  ...fitzOnly,
  tools: [
    ...fitzOnly.tools,
    { tool_id: 'camelot', config: { flavor: 'lattice', edge_tol: 50, row_tol: 2 } },
  ],
}

describe('LocalPipelineConfig', () => {
  it('renders fitz section as always-on and a table-tool selector', () => {
    render(<LocalPipelineConfig config={fitzOnly} onChange={vi.fn()} />)
    expect(screen.getByText(/fitz \(text \+ images\)/i)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /table extraction/i })).toBeInTheDocument()
  })

  it('selecting fitz_tables adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).toContain('fitz_tables')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('camelot')
  })

  it('selecting camelot adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/^camelot/i))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).toContain('camelot')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('fitz_tables')
  })

  it('selecting none removes existing table tool', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={withFitzTables} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByRole('option', { name: /none/i }))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('fitz_tables')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('camelot')
  })

  it('switching from camelot to fitz_tables removes camelot', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={withCamelot} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    const ids = next.tools.map((t: { tool_id: string }) => t.tool_id)
    expect(ids).toContain('fitz_tables')
    expect(ids).not.toContain('camelot')
  })

  it('shows fitz_tables config panel when fitz_tables is selected', () => {
    render(<LocalPipelineConfig config={withFitzTables} onChange={vi.fn()} />)
    expect(screen.getAllByText(/vertical strategy/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/snap tolerance/i).length).toBeGreaterThan(0)
  })

  it('shows camelot flavor select when camelot is selected', () => {
    render(<LocalPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.getByText('Flavor')).toBeInTheDocument()
  })

  it('hides edge_tol/row_tol for camelot lattice flavor', () => {
    render(<LocalPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.queryByText('edge_tol')).not.toBeInTheDocument()
    expect(screen.queryByText('row_tol')).not.toBeInTheDocument()
  })

  it('shows edge_tol/row_tol for camelot stream flavor', () => {
    const withStream = {
      ...fitzOnly,
      tools: [
        ...fitzOnly.tools,
        { tool_id: 'camelot', config: { flavor: 'stream', edge_tol: 50, row_tol: 2 } },
      ],
    }
    render(<LocalPipelineConfig config={withStream} onChange={vi.fn()} />)
    expect(screen.getByText('edge_tol')).toBeInTheDocument()
    expect(screen.getByText('row_tol')).toBeInTheDocument()
  })

  it('shows suggested-tools hint when a profile is provided', () => {
    render(
      <LocalPipelineConfig
        config={fitzOnly}
        onChange={vi.fn()}
        profile={{
          source_document_id: 'd',
          filename: 'x.pdf',
          page_count: 1,
          pages: [],
          has_text_layer: true,
          has_scanned_pages: false,
          has_cid_corruption: false,
          table_signal: true,
          recommended_tools: ['fitz', 'fitz_tables'],
          duration_ms: 10,
          probed_at: '2026-06-25T00:00:00Z',
        }}
      />
    )
    expect(screen.getByText(/fitz, fitz_tables/i)).toBeInTheDocument()
  })
})
