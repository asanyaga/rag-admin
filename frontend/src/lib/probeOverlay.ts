import type { Block } from '@/types/cdm'
import type { ObservationLabel, RegionFinding } from '@/types/probeReport'

export const OBSERVATION_COLORS: Record<ObservationLabel, string> = {
  text_image: 'rgb(37,99,235)',           // blue — OCR candidate
  decorative_image: 'rgb(148,163,184)',   // gray — skip
  text_covered_image: 'rgb(100,116,139)', // slate — skip (text already there)
  uncertain: 'rgb(245,158,11)',           // amber
  table_grid: 'rgb(16,185,129)',          // green
}

export function regionsToBlocks(regions: RegionFinding[]): Block[] {
  return regions.map((r) => ({
    id: r.id,
    page_index: r.page_index,
    bbox: r.bbox,
    role: 'figure',
  }) as Block)
}

export function regionColors(regions: RegionFinding[]): Map<string, string> {
  return new Map(regions.map((r) => [r.id, OBSERVATION_COLORS[r.observation.label]]))
}
