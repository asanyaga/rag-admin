# Prompt Config — Plan 1: Core Abstraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the shared `PromptConfig` type and `resolve_llm_config()` translation function that all subsequent plans depend on, plus the frontend component library (types, hook, editor).

**Architecture:** `PromptConfig` (Pydantic) is the user-expressed LLM config — stored in the DB as JSON, sent over the API. `resolve_llm_config()` translates it into the adapter-facing `LLMConfig`. A shared `<PromptConfigEditor>` React component renders the editor surface for any feature to embed.

**Tech Stack:** Python 3.12 / Pydantic v2 — React 18 / TypeScript / shadcn/ui / Vitest

**Spec:** `docs/superpowers/specs/2026-05-27-unified-prompt-interface-design.md`

**Subsequent plans (all require this one):**
- Plan 2: Playground — `docs/superpowers/plans/2026-05-27-p2-playground.md`
- Plan 3: Evals — `docs/superpowers/plans/2026-05-27-p3-evals.md`
- Plan 4: Classification — `docs/superpowers/plans/2026-05-27-p4-classification.md`
- Plan 5: Extraction — `docs/superpowers/plans/2026-05-27-p5-extraction.md`

---

## File Map

**New backend files:**
- `backend/app/schemas/prompt_config.py` — `ThinkingConfig`, `PromptConfig` Pydantic models
- `backend/app/services/llm/prompt_config.py` — `resolve_llm_config()` translation function
- `backend/tests/services/llm/test_prompt_config.py` — unit tests

**New frontend files:**
- `frontend/src/types/prompt-config.ts` — TypeScript types + provider/model constants
- `frontend/src/hooks/usePromptConfig.ts` — state management hook
- `frontend/src/components/shared/PromptConfigEditor.tsx` — reusable editor component

---

## Task 1: Backend — PromptConfig schema + resolve_llm_config

**Files:**
- Create: `backend/app/schemas/prompt_config.py`
- Create: `backend/app/services/llm/prompt_config.py`
- Create: `backend/tests/services/llm/test_prompt_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/llm/test_prompt_config.py
from app.schemas.prompt_config import PromptConfig, ThinkingConfig
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig


def test_resolve_basic_fields():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=2048)
    result = resolve_llm_config(config)
    assert isinstance(result, LLMConfig)
    assert result.provider == "openai"
    assert result.model == "gpt-4o"
    assert result.temperature == 0.7
    assert result.max_tokens == 2048


def test_resolve_uses_defaults_when_provider_model_null():
    config = PromptConfig()
    result = resolve_llm_config(config, default_provider="anthropic", default_model="claude-sonnet-4-6")
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-6"


def test_resolve_uses_default_temperature_and_tokens():
    config = PromptConfig(provider="openai", model="gpt-4o")
    result = resolve_llm_config(config, default_temperature=0.5, default_max_tokens=2048)
    assert result.temperature == 0.5
    assert result.max_tokens == 2048


def test_resolve_explicit_temperature_overrides_default():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.9)
    result = resolve_llm_config(config, default_temperature=0.0)
    assert result.temperature == 0.9


def test_resolve_structured_output_sets_json_mode():
    config = PromptConfig(provider="openai", model="gpt-4o", structured_output={"type": "object"})
    result = resolve_llm_config(config)
    assert result.json_mode is True


def test_resolve_json_mode_passthrough():
    config = PromptConfig(provider="openai", model="gpt-4o", json_mode=True)
    result = resolve_llm_config(config)
    assert result.json_mode is True


def test_resolve_none_config_returns_defaults():
    result = resolve_llm_config(None, default_provider="openai", default_model="gpt-4o")
    assert result.provider == "openai"
    assert result.model == "gpt-4o"
    assert result.temperature == 0.0
    assert result.max_tokens == 1024


def test_prompt_config_defaults():
    config = PromptConfig()
    assert config.provider is None
    assert config.model is None
    assert config.system_prompt is None
    assert config.temperature is None
    assert config.max_tokens is None
    assert config.thinking is None
    assert config.json_mode is False
    assert config.structured_output is None
    assert config.tools is None


def test_thinking_config_defaults():
    t = ThinkingConfig(enabled=True)
    assert t.effort is None
    assert t.budget_tokens is None
```

- [ ] **Step 2: Run tests — confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_prompt_config.py -v
```

Expected: `ModuleNotFoundError` — the modules don't exist yet.

- [ ] **Step 3: Create the PromptConfig schema**

```python
# backend/app/schemas/prompt_config.py
"""Shared PromptConfig schema used across all LLM-using features."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ThinkingConfig(BaseModel):
    """Provider-agnostic reasoning/thinking control."""
    enabled: bool = True
    effort: Literal["low", "medium", "high"] | None = None
    budget_tokens: int | None = Field(None, alias="budgetTokens")

    model_config = ConfigDict(populate_by_name=True)


class PromptConfig(BaseModel):
    """User-expressed LLM configuration.

    Stores what the user configured. Converted to adapter-ready LLMConfig
    via resolve_llm_config() before being passed to LLM adapters.
    provider/model are nullable — None means use the feature's default.
    """
    system_prompt: str | None = Field(None, alias="systemPrompt")
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(None, alias="maxTokens")
    top_p: float | None = Field(None, alias="topP")
    thinking: ThinkingConfig | None = None
    json_mode: bool = Field(False, alias="jsonMode")
    structured_output: dict | None = Field(None, alias="structuredOutput")
    tools: list[dict] | None = None

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 4: Create resolve_llm_config**

```python
# backend/app/services/llm/prompt_config.py
"""Translates user-expressed PromptConfig into adapter-ready LLMConfig."""
from app.schemas.prompt_config import PromptConfig
from app.services.llm.types import LLMConfig


def resolve_llm_config(
    config: PromptConfig | None,
    default_provider: str = "openai",
    default_model: str = "gpt-4o",
    default_temperature: float = 0.0,
    default_max_tokens: int = 1024,
) -> LLMConfig:
    """Convert a PromptConfig into an adapter-ready LLMConfig.

    Falls back to supplied defaults for any field that is None.
    thinking/tools/top_p are stored on PromptConfig but not yet forwarded
    to adapters — add per-provider translation here when adapters support them.
    """
    if config is None:
        return LLMConfig(
            provider=default_provider,
            model=default_model,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
        )

    return LLMConfig(
        provider=config.provider or default_provider,
        model=config.model or default_model,
        temperature=config.temperature if config.temperature is not None else default_temperature,
        max_tokens=config.max_tokens if config.max_tokens is not None else default_max_tokens,
        json_mode=bool(config.structured_output) or config.json_mode,
    )
```

- [ ] **Step 5: Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_prompt_config.py -v
```

Expected: 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/prompt_config.py backend/app/services/llm/prompt_config.py backend/tests/services/llm/test_prompt_config.py
git commit -m "feat(prompt): add PromptConfig schema and resolve_llm_config"
```

---

## Task 2: Frontend — TypeScript types + usePromptConfig hook

**Files:**
- Create: `frontend/src/types/prompt-config.ts`
- Create: `frontend/src/hooks/usePromptConfig.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/prompt-config.ts
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
```

- [ ] **Step 2: Create usePromptConfig hook**

```typescript
// frontend/src/hooks/usePromptConfig.ts
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
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/prompt-config.ts frontend/src/hooks/usePromptConfig.ts
git commit -m "feat(prompt): add PromptConfig TypeScript types and usePromptConfig hook"
```

---

## Task 3: Frontend — PromptConfigEditor component

**Files:**
- Create: `frontend/src/components/shared/PromptConfigEditor.tsx`

- [ ] **Step 1: Check Collapsible is available**

```
ls frontend/src/components/ui/collapsible.tsx
```

If missing:
```
npx --prefix frontend shadcn@latest add collapsible
```

- [ ] **Step 2: Create the component**

```tsx
// frontend/src/components/shared/PromptConfigEditor.tsx
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PromptConfig, PromptConfigCapabilities } from '@/types/prompt-config'
import { PROVIDERS, PROVIDER_MODEL_OPTIONS, THINKING_PROVIDERS } from '@/types/prompt-config'

interface PromptConfigEditorProps {
  value: PromptConfig
  onChange: (config: PromptConfig) => void
  onProviderChange?: (provider: string) => void
  capabilities?: PromptConfigCapabilities
  className?: string
}

export function PromptConfigEditor({
  value,
  onChange,
  onProviderChange,
  capabilities = {},
  className,
}: PromptConfigEditorProps) {
  const modelOptions = value.provider ? (PROVIDER_MODEL_OPTIONS[value.provider] ?? []) : []
  const supportsThinking = capabilities.thinking && THINKING_PROVIDERS.has(value.provider ?? '')

  const update = (patch: Partial<PromptConfig>) => onChange({ ...value, ...patch })

  return (
    <div className={cn('space-y-4', className)}>
      {/* System Prompt */}
      <div className="space-y-1.5">
        <Label>System Prompt</Label>
        <Textarea
          className="font-mono text-sm min-h-[120px]"
          placeholder="Leave empty to use the default system prompt…"
          value={value.systemPrompt ?? ''}
          onChange={(e) => update({ systemPrompt: e.target.value || undefined })}
        />
      </div>

      {/* Provider + Model */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Provider</Label>
          <Select
            value={value.provider ?? ''}
            onValueChange={(p) => {
              onProviderChange?.(p)
              const models = PROVIDER_MODEL_OPTIONS[p]
              update({ provider: p, model: models?.[0]?.value ?? value.model, thinking: undefined })
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Model</Label>
          {value.provider === 'ollama' ? (
            <Input
              placeholder="e.g. llama3.2"
              value={value.model ?? ''}
              onChange={(e) => update({ model: e.target.value || undefined })}
            />
          ) : (
            <Select
              value={value.model ?? ''}
              onValueChange={(m) => update({ model: m })}
              disabled={!modelOptions.length}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      {/* Temperature */}
      <div className="space-y-1.5">
        <div className="flex justify-between">
          <Label>Temperature</Label>
          <span className="text-sm text-muted-foreground">{value.temperature ?? 0}</span>
        </div>
        <Slider
          min={0}
          max={2}
          step={0.05}
          value={[value.temperature ?? 0]}
          onValueChange={([v]) => update({ temperature: v })}
        />
      </div>

      {/* Max Tokens */}
      <div className="space-y-1.5">
        <Label>Max Tokens</Label>
        <Input
          type="number"
          min={64}
          max={32000}
          value={value.maxTokens ?? ''}
          onChange={(e) => update({ maxTokens: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="1024"
        />
      </div>

      {/* Thinking */}
      {supportsThinking && (
        <div className="space-y-3 border rounded-md p-3">
          <div className="flex items-center justify-between">
            <Label>Thinking / Reasoning</Label>
            <Switch
              checked={value.thinking?.enabled ?? false}
              onCheckedChange={(checked) =>
                update({ thinking: checked ? { enabled: true } : undefined })
              }
            />
          </div>
          {value.thinking?.enabled && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Effort</Label>
                <Select
                  value={value.thinking.effort ?? ''}
                  onValueChange={(v) =>
                    update({ thinking: { ...value.thinking!, effort: v as 'low' | 'medium' | 'high' } })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Budget Tokens</Label>
                <Input
                  type="number"
                  min={1024}
                  placeholder="e.g. 4000"
                  value={value.thinking.budgetTokens ?? ''}
                  onChange={(e) =>
                    update({
                      thinking: {
                        ...value.thinking!,
                        budgetTokens: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Advanced */}
      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className="h-3 w-3" />
          Advanced
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3 space-y-3">
          <div className="space-y-1.5">
            <Label>Top P</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              placeholder="1.0"
              value={value.topP ?? ''}
              onChange={(e) => update({ topP: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
          {capabilities.structuredOutput && (
            <div className="space-y-1.5">
              <Label>Structured Output Schema (JSON)</Label>
              <Textarea
                className="font-mono text-sm min-h-[80px]"
                placeholder='{"type": "object", "properties": {...}}'
                value={value.structuredOutput ? JSON.stringify(value.structuredOutput, null, 2) : ''}
                onChange={(e) => {
                  try {
                    const parsed = e.target.value ? JSON.parse(e.target.value) : undefined
                    update({ structuredOutput: parsed })
                  } catch {
                    // Invalid JSON — don't update until valid
                  }
                }}
              />
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
```

- [ ] **Step 3: Lint + build**

```
npm --prefix frontend run lint
npm --prefix frontend run build
```

Fix any errors before continuing.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/PromptConfigEditor.tsx
git commit -m "feat(prompt): add PromptConfigEditor shared component"
```
