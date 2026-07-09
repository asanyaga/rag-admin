import type { Signal } from '@/types/probeReport'

export function SignalReceipt({ signal }: { signal: Signal }) {
  const pct = signal.strength == null ? null : Math.round(signal.strength * 100)
  return (
    <div className="grid grid-cols-[110px_60px_1fr] items-center gap-2 text-xs py-0.5">
      <span className="text-muted-foreground">{signal.name}</span>
      <span className="font-mono tabular-nums">
        {String(signal.value)}
        {signal.unit === '%' ? '%' : ''}
      </span>
      <div className="h-1.5 rounded bg-muted overflow-hidden">
        {pct != null && <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />}
      </div>
    </div>
  )
}
