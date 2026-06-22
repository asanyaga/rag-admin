export interface RunColorSet {
  card: string
  headerTop: string
  cellBg: string
  groupBorder: string
}

const PALETTE: RunColorSet[] = [
  { card: 'border-l-indigo-500',  headerTop: 'border-t-indigo-500',  cellBg: 'bg-indigo-50/60',  groupBorder: 'border-l-indigo-300' },
  { card: 'border-l-emerald-500', headerTop: 'border-t-emerald-500', cellBg: 'bg-emerald-50/60', groupBorder: 'border-l-emerald-300' },
  { card: 'border-l-amber-500',   headerTop: 'border-t-amber-500',   cellBg: 'bg-amber-50/60',   groupBorder: 'border-l-amber-300' },
  { card: 'border-l-rose-500',    headerTop: 'border-t-rose-500',    cellBg: 'bg-rose-50/60',    groupBorder: 'border-l-rose-300' },
  { card: 'border-l-violet-500',  headerTop: 'border-t-violet-500',  cellBg: 'bg-violet-50/60',  groupBorder: 'border-l-violet-300' },
  { card: 'border-l-sky-500',     headerTop: 'border-t-sky-500',     cellBg: 'bg-sky-50/60',     groupBorder: 'border-l-sky-300' },
]

export const BASELINE_COLOR: RunColorSet = {
  card: 'border-l-slate-400',
  headerTop: 'border-t-slate-400',
  cellBg: 'bg-slate-50/60',
  groupBorder: 'border-l-slate-300',
}

export function getRunColor(index: number): RunColorSet {
  return PALETTE[index % PALETTE.length]
}
