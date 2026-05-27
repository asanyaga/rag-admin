import { useState, useCallback } from 'react'
import type { PromptConfig } from '@/types/prompt-config'
import { DEFAULT_PROMPT_CONFIG, PROVIDER_MODEL_OPTIONS } from '@/types/prompt-config'

export function usePromptConfig(initial?: Partial<PromptConfig>) {
  const [promptConfig, setPromptConfig] = useState<PromptConfig>({
    ...DEFAULT_PROMPT_CONFIG,
    ...initial,
  })

  const updatePromptConfig = useCallback((updates: Partial<PromptConfig>) => {
    setPromptConfig((prev) => ({ ...prev, ...updates }))
  }, [])

  const setProvider = useCallback((provider: string) => {
    const models = PROVIDER_MODEL_OPTIONS[provider]
    const firstModel = models?.[0]?.value
    setPromptConfig((prev) => ({
      ...prev,
      provider,
      model: firstModel ?? prev.model,
      thinking: undefined,
    }))
  }, [])

  const resetToDefaults = useCallback(() => {
    setPromptConfig({ ...DEFAULT_PROMPT_CONFIG, ...initial })
  }, [initial])

  return { promptConfig, setPromptConfig, updatePromptConfig, setProvider, resetToDefaults }
}
