import { describe, it, expect } from 'vitest'
import { nodeState } from './GraphStrip'
import type { ParseAgentRunStatus, ParseAgentRunStep } from '@/types/parseAgent'

function step(node: string): ParseAgentRunStep {
  return {
    id: `step-${node}`,
    seq: 0,
    node,
    phase: 'end',
    status: 'succeeded',
    inputKeys: [],
    outputKeys: [],
    stateDelta: {},
    message: null,
    durationMs: 100,
    createdAt: '2026-07-17T10:00:00Z',
  }
}

const graphNodes = ['parse', 'health_check', 'finalize']

describe('nodeState', () => {
  const cases: Array<{
    name: string
    node: string
    steps: ParseAgentRunStep[]
    runStatus: ParseAgentRunStatus
    expected: 'done' | 'running' | 'failed' | 'pending'
  }> = [
    {
      name: 'a node with a step is done',
      node: 'parse',
      steps: [step('parse')],
      runStatus: 'running',
      expected: 'done',
    },
    {
      name: 'the first node without a step is running when the run is running',
      node: 'parse',
      steps: [],
      runStatus: 'running',
      expected: 'running',
    },
    {
      name: 'the first node without a step is failed when the run failed',
      node: 'parse',
      steps: [],
      runStatus: 'failed',
      expected: 'failed',
    },
    {
      name: 'the first node without a step is pending when the run completed',
      node: 'parse',
      steps: [],
      runStatus: 'completed',
      expected: 'pending',
    },
    {
      name: 'a later node without a step stays pending even when an earlier one also lacks a step',
      node: 'health_check',
      steps: [],
      runStatus: 'failed',
      expected: 'pending',
    },
  ]

  it.each(cases)('$name', ({ node, steps, runStatus, expected }) => {
    expect(nodeState(node, graphNodes, steps, runStatus)).toBe(expected)
  })
})
