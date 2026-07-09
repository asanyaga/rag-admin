import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { PageCard } from './PageCard'
import type { PageProfile } from '@/types/probeReport'

const page: PageProfile = {
  index: 3, page_type: 'scanned',
  signals: [{ name: 'font_health', value: 'clean', unit: null, strength: 1, detail: null }],
  regions: [{
    id: 'p3:img0', page_index: 3, kind: 'image',
    bbox: { x0: 0, y0: 0, x1: 1, y1: 1 },
    signals: [{ name: 'edge_density', value: 0.21, unit: 'fraction', strength: 0.85, detail: 'sobel' }],
    observation: { label: 'text_image', confidence: 0.88 },
  }],
}

describe('PageCard', () => {
  it('shows page number, type, and region observation with confidence', () => {
    render(<PageCard page={page} selected={false} onSelect={() => {}} />)
    expect(screen.getByText(/Page 4/)).toBeInTheDocument()   // index 3 -> "Page 4"
    expect(screen.getByText(/scanned/)).toBeInTheDocument()
    expect(screen.getByText(/text_image/)).toBeInTheDocument()
    expect(screen.getByText(/0\.88/)).toBeInTheDocument()
    expect(screen.getByText(/edge_density/)).toBeInTheDocument()
  })
})
