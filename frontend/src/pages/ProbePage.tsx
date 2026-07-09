import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { useProbe } from '@/hooks/useProbe'
import { DocumentPickerPanel } from '@/components/shared/DocumentPickerPanel'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { ProbeReportView } from '@/components/probe/ProbeReportView'
import { SignalsPopover, DEFAULT_PROBE_CONFIG } from '@/components/probe/SignalsPopover'
import { regionsToBlocks, regionColors } from '@/lib/probeOverlay'
import type { ProbeConfig } from '@/types/probeReport'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FileSearch } from 'lucide-react'

export default function ProbePage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const { documents, isLoading } = useDocuments(projectId)
  const { folders } = useFolders(projectId)
  const { report, isLoading: probing, error, run } = useProbe()

  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [selectedPage, setSelectedPage] = useState<number | null>(null)
  const [config, setConfig] = useState<ProbeConfig>(DEFAULT_PROBE_CONFIG)

  const selectDoc = (id: string) => {
    setSelectedDocumentId(id)
    setSelectedPage(null)
    run(id, config)
  }

  if (!currentProject) {
    return (
      <div className="p-6">
        <Alert><AlertDescription>Loading project...</AlertDescription></Alert>
      </div>
    )
  }

  const regions = report?.pages.flatMap((p) => p.regions) ?? []
  const blocks = regionsToBlocks(regions)
  const colors = regionColors(regions)

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Probe</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
        {selectedDocumentId && (
          <SignalsPopover
            config={config}
            onChange={setConfig}
            onRerun={() => selectedDocumentId && run(selectedDocumentId, config)}
          />
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="w-64 border-r shrink-0 flex flex-col">
          <DocumentPickerPanel
            documents={documents}
            folders={folders}
            isLoading={isLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={selectDoc}
            onUploadClick={() => {}}
          />
        </div>

        {!selectedDocumentId ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center">
            <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
            <h2 className="text-lg font-medium text-muted-foreground">Select a document to probe</h2>
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            <div className="flex-1 min-w-0 border-r">
              <DocumentPdfViewer
                documentId={selectedDocumentId}
                blocks={blocks}
                selectedBlockId={null}
                onBlockSelect={() => {}}
                blockColors={colors}
                selectedPageIndex={selectedPage}
              />
            </div>
            <div className="w-[420px] shrink-0 overflow-hidden">
              {error && <div className="p-4 text-sm text-destructive">{error}</div>}
              {probing && <div className="p-4 text-sm text-muted-foreground">Probing…</div>}
              {report && (
                <ProbeReportView report={report} selectedPage={selectedPage} onSelectPage={setSelectedPage} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
