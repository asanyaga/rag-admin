import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRunDetail } from '@/hooks/useEvalRuns'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { ClaimBreakdown } from '@/components/evaluation/ClaimBreakdown'
import { RetrievedChunksList } from '@/components/evaluation/RetrievedChunksList'
import { ExpectedSourcesList } from '@/components/evaluation/ExpectedSourcesList'
import { ChunkDetailPanel } from '@/components/shared/ChunkDetailPanel'
import { QueryTracePanel } from '@/components/indexes/QueryTracePanel'
import type { RetrievedChunk } from '@/types/eval-run'

export default function EvalResultDetailPage() {
  const { runId, resultId } = useParams<{ runId: string; resultId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { run, results, isLoading } = useEvalRunDetail(projectId, runId ?? null)

  const [selectedChunk, setSelectedChunk] = useState<RetrievedChunk | null>(null)

  const currentIndex = useMemo(
    () => results.findIndex((r) => r.id === resultId),
    [results, resultId]
  )
  const result = currentIndex >= 0 ? results[currentIndex] : null
  const prevId = currentIndex > 0 ? results[currentIndex - 1].id : null
  const nextId = currentIndex < results.length - 1 ? results[currentIndex + 1].id : null

  const isAnswerMode = run?.mode === 'retrieval_and_answer'

  if (isLoading || !run) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!result) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(`/evaluation/runs/${runId}`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <p className="text-muted-foreground text-center py-8">Result not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with nav */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(`/evaluation/runs/${runId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate">{result.queryText}</h1>
          <p className="text-xs text-muted-foreground">{run.name}</p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            disabled={!prevId}
            onClick={() => prevId && navigate(`/evaluation/runs/${runId}/results/${prevId}`)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground tabular-nums px-1">
            {currentIndex + 1} / {results.length}
          </span>
          <Button
            variant="outline"
            size="icon"
            disabled={!nextId}
            onClick={() => nextId && navigate(`/evaluation/runs/${runId}/results/${nextId}`)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Score summary bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Precision</span>
          <ScorePill score={result.precision} />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Recall</span>
          <ScorePill score={result.recall} />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">F1</span>
          <ScorePill score={result.f1} />
        </div>
        {isAnswerMode && (
          <>
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Faithfulness</span>
              <ScorePill score={result.faithfulnessScore} />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Relevance</span>
              <ScorePill score={result.relevanceScore} />
            </div>
          </>
        )}
      </div>

      {/* Error banners */}
      {result.generationError && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Generation Error</p>
            <p className="text-xs mt-0.5">{result.generationError}</p>
          </div>
        </div>
      )}
      {result.judgeError && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-400">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Judge Error</p>
            <p className="text-xs mt-0.5">{result.judgeError}</p>
          </div>
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left column — wider */}
        <div className="lg:col-span-3 space-y-6">
          {/* Generated Answer */}
          {isAnswerMode && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">Generated Answer</CardTitle>
                  {run.generationConfig?.model && (
                    <Badge variant="secondary" className="text-xs font-normal">
                      {run.generationConfig.provider}/{run.generationConfig.model}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {result.generatedAnswer ? (
                  <p className="text-sm whitespace-pre-wrap">{result.generatedAnswer}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">No answer generated.</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Claim Breakdown */}
          {isAnswerMode && result.claimBreakdown && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Claim Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <ClaimBreakdown claims={result.claimBreakdown} />
              </CardContent>
            </Card>
          )}

          {/* Query Trace */}
          {result.traceData && (
            <QueryTracePanel trace={result.traceData} />
          )}
        </div>

        {/* Right column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Retrieved Chunks */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Retrieved Chunks</CardTitle>
                <span className="text-xs text-muted-foreground">
                  {result.retrievedChunks.length} chunk{result.retrievedChunks.length !== 1 ? 's' : ''}
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <RetrievedChunksList
                chunks={result.retrievedChunks}
                selectedChunkId={selectedChunk?.chunkId}
                onChunkClick={(chunk) =>
                  setSelectedChunk(
                    selectedChunk?.chunkId === chunk.chunkId ? null : chunk
                  )
                }
              />
            </CardContent>
          </Card>

          {/* Expected Sources */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Expected Sources</CardTitle>
            </CardHeader>
            <CardContent>
              <ExpectedSourcesList
                sources={result.expectedSources}
                retrievedChunks={result.retrievedChunks}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Chunk Detail Sheet */}
      <Sheet
        open={!!selectedChunk}
        onOpenChange={(open) => {
          if (!open) setSelectedChunk(null)
        }}
      >
        <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              Chunk Detail
              {selectedChunk && (
                <Badge variant="outline" className="font-mono text-xs">
                  Rank #{selectedChunk.rank}
                </Badge>
              )}
            </SheetTitle>
            <SheetDescription>
              {selectedChunk?.documentName}
            </SheetDescription>
          </SheetHeader>

          {selectedChunk && projectId && (
            <div className="mt-4">
              <ChunkDetailPanel
                projectId={projectId}
                indexId={run.indexId}
                chunkId={selectedChunk.chunkId}
                header={
                  <div className="flex items-center gap-3 pb-3 border-b">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">Score</span>
                      <span className="text-sm font-mono font-medium">
                        {(selectedChunk.score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">Relevant</span>
                      {selectedChunk.isRelevant ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-400" />
                      )}
                    </div>
                    {selectedChunk.page != null && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Page</span>
                        <span className="text-sm font-mono">{selectedChunk.page}</span>
                      </div>
                    )}
                  </div>
                }
              />
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
