import type { ProbeReport } from '@/types/probeReport'
import { PageCard } from './PageCard'
import { SuggestionPanel } from './SuggestionPanel'

interface Props {
  report: ProbeReport
  selectedPage: number | null
  onSelectPage: (index: number) => void
}

export function ProbeReportView({ report, selectedPage, onSelectPage }: Props) {
  return (
    <div className="p-4 overflow-y-auto h-full">
      {report.suggestion && <SuggestionPanel suggestion={report.suggestion} />}
      {report.pages.map((page) => (
        <PageCard
          key={page.index}
          page={page}
          selected={selectedPage === page.index}
          onSelect={onSelectPage}
        />
      ))}
    </div>
  )
}
