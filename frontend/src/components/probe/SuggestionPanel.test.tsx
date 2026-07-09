import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SuggestionPanel } from './SuggestionPanel'

describe('SuggestionPanel', () => {
  it('renders tools, rationale, and the advisory disclaimer', () => {
    render(<SuggestionPanel suggestion={{
      authoritative: false, tools: ['fitz', 'fitz_tables'], ocr_pages: [3],
      overall_confidence: 0.81,
      rationale: ['Base extractor fitz.', 'Text-like images on pages [3] -> OCR suggested.'],
    }} />)
    expect(screen.getByText(/Suggested parse configuration/i)).toBeInTheDocument()
    expect(screen.getByText(/not authoritative/i)).toBeInTheDocument()
    expect(screen.getByText('fitz_tables')).toBeInTheDocument()
    expect(screen.getByText(/OCR suggested/)).toBeInTheDocument()
  })
})
