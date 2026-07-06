import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ParserComparisonTable } from './ParserComparisonTable'
import type { ParserEvalResult } from '@/types/parserEval'

const results: ParserEvalResult[] = [
  { evalCaseId: 'c1', adapter: 'custom_pipeline', config: {}, variantKey: 'custom_pipeline@a',
    metrics: { similarity: 0.90, omission: 0.05, hallucination: 0.02 }, primaryMetric: 'similarity',
    details: null, cost: { usd: 0 }, latencyMs: 140 },
  { evalCaseId: 'c1', adapter: 'docling', config: {}, variantKey: 'docling@b',
    metrics: { similarity: 0.97, omission: 0.01, hallucination: 0.02 }, primaryMetric: 'similarity',
    details: null, cost: { usd: 0 }, latencyMs: 890 },
]

describe('ParserComparisonTable', () => {
  it('groups by case and orders adapters by similarity desc', () => {
    render(<ParserComparisonTable results={results} caseLabels={{ c1: 'acme.pdf' }} />)
    expect(screen.getByText('acme.pdf · text')).toBeInTheDocument()
    const rows = screen.getAllByTestId('cmp-row')
    // best-first: docling (0.97) before custom_pipeline (0.90)
    expect(within(rows[0]).getByText('Docling')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Custom pipeline')).toBeInTheDocument()
  })
})
