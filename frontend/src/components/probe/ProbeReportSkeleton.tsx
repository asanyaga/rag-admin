import { Skeleton } from '@/components/ui/skeleton'

function SignalRowSkeleton() {
  return (
    <div className="grid grid-cols-[110px_60px_1fr] items-center gap-2 py-0.5">
      <Skeleton className="h-2.5 w-16" />
      <Skeleton className="h-2.5 w-8" />
      <Skeleton className="h-1.5 w-full" />
    </div>
  )
}

function RegionCardSkeleton() {
  return (
    <div className="rounded border p-2 mb-1.5">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3.5 w-24 rounded-full" />
      </div>
      <SignalRowSkeleton />
      <SignalRowSkeleton />
      <SignalRowSkeleton />
    </div>
  )
}

function PageCardSkeleton({ regions }: { regions: number }) {
  return (
    <div className="rounded-md border p-3 mb-2">
      <div className="flex items-center gap-2 mb-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-3 w-14" />
      </div>
      <div className="flex gap-1 mb-2">
        <Skeleton className="h-3 w-20 rounded-full" />
        <Skeleton className="h-3 w-16 rounded-full" />
      </div>
      {Array.from({ length: regions }, (_, i) => <RegionCardSkeleton key={i} />)}
    </div>
  )
}

/** Mirrors ProbeReportView's structure so the layout does not jump when results land. */
export function ProbeReportSkeleton() {
  return (
    <div className="p-4 overflow-y-auto h-full" data-testid="probe-report-skeleton">
      <p className="text-xs text-muted-foreground mb-3">Probing document…</p>

      {/* Suggested parse configuration panel */}
      <div className="rounded-md border bg-muted/30 p-3 mb-4">
        <div className="flex items-center justify-between mb-2">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-3 w-24" />
        </div>
        <div className="flex gap-1 mb-3">
          <Skeleton className="h-4 w-14 rounded-full" />
          <Skeleton className="h-4 w-20 rounded-full" />
          <Skeleton className="h-4 w-24 rounded-full" />
        </div>
        <Skeleton className="h-2.5 w-full mb-1" />
        <Skeleton className="h-2.5 w-11/12 mb-1" />
        <Skeleton className="h-2.5 w-4/5" />
      </div>

      <PageCardSkeleton regions={1} />
      <PageCardSkeleton regions={2} />
      <PageCardSkeleton regions={1} />
    </div>
  )
}
