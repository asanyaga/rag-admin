import type { PromptConfig } from '@/types/prompt-config'

export function buildClassifierConfig(
  classifierType: string,
  promptConfig: PromptConfig,
  batchSize: number,
  batchOverlap: number,
): Record<string, unknown> {
  if (classifierType !== 'llm') return {}
  return {
    provider: promptConfig.provider,
    model: promptConfig.model,
    batch_size: batchSize,
    batch_overlap: batchOverlap,
    llm_config: {
      system_prompt: promptConfig.systemPrompt ?? null,
      temperature: promptConfig.temperature ?? 0.0,
      max_tokens: promptConfig.maxTokens ?? 4096,
    },
  }
}
