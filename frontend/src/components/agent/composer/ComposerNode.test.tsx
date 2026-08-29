import { render, screen } from '@testing-library/react'
import { ReactFlowProvider } from '@xyflow/react'
import { describe, it, expect } from 'vitest'
import { ComposerNode } from './ComposerNode'

function renderNode(data: Record<string, unknown>) {
  return render(
    <ReactFlowProvider>
      <ComposerNode id="n1" data={data as never} selected={false} />
    </ReactFlowProvider>
  )
}

describe('ComposerNode unmet-input warning', () => {
  it('shows an unmet-input warning when the node has missing inputs', () => {
    renderNode({ label: 'Export', toolSlug: 'export', category: 'export', config: {},
                 unmetInputs: ['Extracted data'] })
    expect(screen.getByText(/extracted data/i)).toBeInTheDocument()
  })

  it('shows no warning when inputs are satisfied', () => {
    renderNode({ label: 'Export', toolSlug: 'export', category: 'export', config: {}, unmetInputs: [] })
    expect(screen.queryByText(/needs/i)).not.toBeInTheDocument()
  })
})
