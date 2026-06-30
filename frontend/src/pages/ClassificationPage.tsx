import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tags } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { DocumentSelector } from '@/components/extraction/DocumentSelector'
import { ClassificationRunHistory } from '@/components/classification/ClassificationRunHistory'
import { ClassificationRunDetail } from '@/components/classification/ClassificationRunDetail'
import { ClassificationRunSheet } from '@/components/classification/ClassificationRunSheet'
import type { RerunDefaults } from '@/components/classification/ClassificationRunDetail'

export default function ClassificationPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { documents, isLoading: documentsLoading } = useDocuments(projectId)

  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetDefaults, setSheetDefaults] = useState<RerunDefaults | undefined>()

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSelectedRunId(null)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleNewRun = () => {
    setSheetDefaults(undefined)
    setSheetOpen(true)
  }

  const handleRerun = (defaults: RerunDefaults) => {
    setSheetDefaults(defaults)
    setSheetOpen(true)
  }

  const handleRunStarted = (runId: string) => {
    setSelectedRunId(runId)
    setSheetOpen(false)
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Classify</h1>
          <p className="text-xs text-muted-foreground">{currentProject?.name}</p>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left: document picker */}
        <div className="w-56 border-r shrink-0 flex flex-col">
          <DocumentSelector
            documents={documents}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
          />
        </div>

        {/* Right: run history + detail */}
        <div className="flex-1 min-h-0 flex flex-col">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <Tags className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">
                Select a document to get started
              </h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list to see its classification history.
              </p>
            </div>
          ) : (
            <>
              <ClassificationRunHistory
                documentId={selectedDocumentId}
                selectedRunId={selectedRunId}
                onSelectRun={setSelectedRunId}
                onNewRun={handleNewRun}
              />
              <div className="flex-1 min-h-0 overflow-hidden">
                {selectedRunId ? (
                  <ClassificationRunDetail
                    runId={selectedRunId}
                    documentId={selectedDocumentId}
                    onRerun={handleRerun}
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center px-6">
                    <p className="text-sm text-muted-foreground">
                      Select a run above, or{' '}
                      <button
                        className="underline hover:no-underline"
                        onClick={handleNewRun}
                      >
                        start a new one
                      </button>
                      .
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* New-run sheet */}
      {selectedDocumentId && (
        <ClassificationRunSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          documentId={selectedDocumentId}
          documentTitle={selectedDocument?.title ?? ''}
          defaultValues={sheetDefaults}
          onStarted={handleRunStarted}
        />
      )}
    </div>
  )
}
