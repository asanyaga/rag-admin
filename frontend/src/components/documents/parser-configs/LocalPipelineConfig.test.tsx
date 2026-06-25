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

describe('LocalPipelineConfig', () => {
  it('renders fitz as always-on and camelot as a toggle', () => {
    render(<LocalPipelineConfig config={fitzOnly} onChange={vi.fn()} />)
    expect(screen.getByText(/fitz \(text \+ images\)/i)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /camelot/i })).toBeInTheDocument()
  })

  it('adds camelot to tools when toggled on', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: /camelot/i }))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).toContain('camelot')
  })

  it('removes camelot when toggled off', async () => {
    const onChange = vi.fn()
    const withCamelot = {
      ...fitzOnly,
      tools: [
        ...fitzOnly.tools,
        { tool_id: 'camelot', config: { flavor: 'lattice', edge_tol: 50, row_tol: 2 } },
      ],
    }
    render(<LocalPipelineConfig config={withCamelot} onChange={onChange} />)
    await userEvent.click(screen.getByRole('checkbox', { name: /camelot/i }))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('camelot')
  })

  it('shows camelot flavor select when camelot is enabled', () => {
    const withCamelot = {
      ...fitzOnly,
      tools: [
        ...fitzOnly.tools,
        { tool_id: 'camelot', config: { flavor: 'lattice', edge_tol: 50, row_tol: 2 } },
      ],
    }
    render(<LocalPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.getByText('Flavor')).toBeInTheDocument()
  })

  it('shows a suggested-tools hint when a profile is provided', () => {
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
          recommended_tools: ['fitz', 'camelot'],
          duration_ms: 10,
          probed_at: '2026-06-25T00:00:00Z',
        }}
      />
    )
    expect(screen.getByText(/fitz, camelot/i)).toBeInTheDocument()
  })
})
