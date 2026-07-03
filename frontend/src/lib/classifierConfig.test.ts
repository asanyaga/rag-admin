import { describe, expect, it } from 'vitest'
import { buildClassifierConfig } from './classifierConfig'

const prompt = { provider: 'openai', model: 'gpt', temperature: 0.2, maxTokens: 100, systemPrompt: 'sp' }

describe('buildClassifierConfig', () => {
  it('builds llm config from prompt + batch settings', () => {
    expect(buildClassifierConfig('llm', prompt as never, 10, 3)).toEqual({
      provider: 'openai', model: 'gpt', batch_size: 10, batch_overlap: 3,
      llm_config: { system_prompt: 'sp', temperature: 0.2, max_tokens: 100 },
    })
  })

  it('returns empty object for non-llm classifier', () => {
    expect(buildClassifierConfig('llamaindex_split', prompt as never, 10, 3)).toEqual({})
  })
})
