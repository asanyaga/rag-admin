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

const one = (over: Partial<ParserEvalResult>): ParserEvalResult => ({
  evalCaseId: 'c1', adapter: 'docling', config: {}, variantKey: 'docling@x',
  metrics: {}, primaryMetric: null, details: null, cost: null, latencyMs: 100, ...over,
})

describe('ParserComparisonTable', () => {
  it('groups by case and orders adapters by similarity desc', () => {
    render(<ParserComparisonTable results={results} caseLabels={{ c1: 'acme.pdf' }} />)
    expect(screen.getByText('acme.pdf · text')).toBeInTheDocument()
    const rows = screen.getAllByTestId('cmp-row')
    // best-first: docling (0.97) before custom_pipeline (0.90)
    expect(within(rows[0]).getByText('Docling')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Custom pipeline')).toBeInTheDocument()
  })

  it('renders TEDS columns for a table case', () => {
    render(<ParserComparisonTable
      results={[one({ metrics: { teds: 0.9, table_recall: 1 }, primaryMetric: 'teds' })]}
      caseLabels={{ c1: 'a.pdf' }} caseDimensions={{ c1: 'table' }} />)
    expect(screen.getByText('TEDS')).toBeInTheDocument()
    expect(screen.getByText('Table recall')).toBeInTheDocument()
  })

  it('renders text columns for a text case', () => {
    render(<ParserComparisonTable
      results={[one({ metrics: { similarity: 0.8, omission: 0.1, hallucination: 0 }, primaryMetric: 'similarity' })]}
      caseLabels={{ c1: 'a.pdf' }} caseDimensions={{ c1: 'text' }} />)
    expect(screen.getByText('Similarity')).toBeInTheDocument()
    expect(screen.getByText('Hallucination')).toBeInTheDocument()
  })
})
