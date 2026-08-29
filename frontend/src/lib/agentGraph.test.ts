import { describe, it, expect } from 'vitest'
import { validateGraph, deriveRunFormFields } from './agentGraph'
import type { AgentTool } from '@/types/agent'

const tool = (slug: string, runtimeInputs: AgentTool['runtimeInputs'], outputs: string[]): AgentTool => ({
  slug, name: slug, category: 'x', description: '', runtimeInputs, outputs,
  configSchema: {}, configPanel: null,
})

const TOOLS: AgentTool[] = [
  tool('llamaextract',
    [{ key: 'document_id', label: 'Document', widget: 'document_picker', source: 'form' },
     { key: 'extraction_schema_id', label: 'Schema', widget: 'extraction_schema_picker', source: 'form' }],
    ['extracted_data']),
  tool('human-review',
    [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    ['review_action', 'reviewed_data']),
  tool('export',
    [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    ['exported', 'rows_exported']),
]

describe('validateGraph', () => {
  it('valid extract->review->export has no unmet', () => {
    const nodes = [{ id: 'e', tool: 'llamaextract' }, { id: 'r', tool: 'human-review' }, { id: 'x', tool: 'export' }]
    const edges = [{ source: 'e', target: 'r' }, { source: 'r', target: 'x' }]
    expect(validateGraph(nodes, edges, TOOLS)).toEqual([])
  })

  it('lone export has unmet extracted_data', () => {
    expect(validateGraph([{ id: 'x', tool: 'export' }], [], TOOLS))
      .toEqual([{ nodeId: 'x', key: 'extracted_data' }])
  })

  it('producer after consumer does not satisfy', () => {
    const nodes = [{ id: 'x', tool: 'export' }, { id: 'e', tool: 'llamaextract' }]
    const edges = [{ source: 'x', target: 'e' }] // export before extract
    expect(validateGraph(nodes, edges, TOOLS)).toContainEqual({ nodeId: 'x', key: 'extracted_data' })
  })
})

describe('deriveRunFormFields', () => {
  it('extract chain prompts document + schema only (not extracted_data)', () => {
    const nodes = [{ id: 'e', tool: 'llamaextract' }, { id: 'r', tool: 'human-review' }, { id: 'x', tool: 'export' }]
    const keys = deriveRunFormFields(nodes, TOOLS).map((f) => f.key)
    expect(keys).toEqual(['document_id', 'extraction_schema_id'])
  })
})
