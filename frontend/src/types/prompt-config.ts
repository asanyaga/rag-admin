export interface ThinkingConfig {
  enabled: boolean
  effort?: 'low' | 'medium' | 'high'
  budgetTokens?: number
}

export interface PromptConfig {
  systemPrompt?: string
  provider?: string
  model?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  thinking?: ThinkingConfig
  jsonMode?: boolean
  structuredOutput?: Record<string, unknown>
  tools?: unknown[]
}

export interface PromptConfigCapabilities {
  thinking?: boolean
  structuredOutput?: boolean
  tools?: boolean
}

export const PROVIDER_MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4.1', label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'o3', label: 'o3' },
    { value: 'o4-mini', label: 'o4-mini' },
  ],
  anthropic: [
    { value: 'claude-opus-4-7', label: 'Claude Opus 4.7' },
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
  ],
  ollama: [],
}

export const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama (local)' },
]

export const THINKING_PROVIDERS = new Set(['openai', 'anthropic', 'deepseek'])

export const DEFAULT_PROMPT_CONFIG: PromptConfig = {
  provider: 'openai',
  model: 'gpt-4o',
  temperature: 0.0,
  maxTokens: 1024,
}
