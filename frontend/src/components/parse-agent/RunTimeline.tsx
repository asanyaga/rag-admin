import type { ParseAgentRunStep } from '@/types/parseAgent'

interface RunTimelineProps {
  steps: ParseAgentRunStep[]
  selectedStepId: string | null
  onSelectStep: (step: ParseAgentRunStep) => void
}

export function RunTimeline({
  steps,
  selectedStepId,
  onSelectStep,
}: RunTimelineProps): JSX.Element {
  if (steps.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        No steps yet — waiting for the run to produce its first step.
      </p>
    )
  }

  return (
    <ol className="space-y-1 p-2">
      {steps.map((step) => (
        <li key={step.id}>
          <button
            type="button"
            onClick={() => onSelectStep(step)}
            className={`w-full rounded-md border p-3 text-left transition-colors hover:bg-muted/50 ${
              selectedStepId === step.id
                ? 'border-primary bg-primary/5'
                : 'border-transparent'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{step.node}</span>
              <span className="text-xs text-muted-foreground">
                {step.durationMs !== null ? `${step.durationMs} ms` : ''}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              read {step.inputKeys.join(', ') || '—'} → wrote{' '}
              {step.outputKeys.join(', ') || '—'}
            </p>
            {step.message ? (
              <p className="mt-1 text-xs text-muted-foreground">{step.message}</p>
            ) : null}
          </button>
        </li>
      ))}
    </ol>
  )
}
