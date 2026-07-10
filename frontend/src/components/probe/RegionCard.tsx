import type { RegionFinding } from '@/types/probeReport'
import { OBSERVATION_COLORS } from '@/lib/probeOverlay'
import { SignalReceipt } from './SignalReceipt'

export function RegionCard({ region }: { region: RegionFinding }) {
  const color = OBSERVATION_COLORS[region.observation.label]
  return (
    <div className="rounded border p-2 mb-1.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium">{region.id}</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full text-white" style={{ background: color }}>
          {region.observation.label} · {region.observation.confidence.toFixed(2)}
        </span>
      </div>
      {region.signals.map((s) => (
        <SignalReceipt key={s.name} signal={s} />
      ))}
    </div>
  )
}
