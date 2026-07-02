import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { getAccessToken } from '@/api/client'
import type { Block } from '@/types/cdm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChevronLeft, ChevronRight } from 'lucide-react'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const ROLE_COLOR: Record<string, string> = {
  title: 'rgb(59,130,246)',
  heading: 'rgb(99,102,241)',
  text: 'rgb(107,114,128)',
  list: 'rgb(245,158,11)',
  table: 'rgb(16,185,129)',
  figure: 'rgb(139,92,246)',
  caption: 'rgb(249,115,22)',
  header: 'rgb(148,163,184)',
  footer: 'rgb(148,163,184)',
  code: 'rgb(6,182,212)',
  formula: 'rgb(236,72,153)',
  other: 'rgb(107,114,128)',
}
const DEFAULT_COLOR = 'rgb(107,114,128)'

interface DocumentPdfViewerProps {
  documentId: string
  blocks: Block[]
  selectedBlockId: string | null
  onBlockSelect: (blockId: string) => void
  blockColors?: Map<string, string>
  selectedPageIndex?: number | null
}

export function DocumentPdfViewer({
  documentId,
  blocks,
  selectedBlockId,
  onBlockSelect,
  blockColors,
  selectedPageIndex,
}: DocumentPdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageInput, setPageInput] = useState<string>('1')
  const [loadError, setLoadError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<(HTMLDivElement | null)[]>([])

  const pdfFile = useMemo(
    () => ({
      url: `${API_BASE_URL}/documents/${documentId}/file`,
      httpHeaders: (() => {
        const token = getAccessToken()
        return token ? { Authorization: `Bearer ${token}` } : {}
      })(),
    }),
    [documentId],
  )

  useEffect(() => {
    if (!selectedBlockId) return
    const block = blocks.find((b) => b.id === selectedBlockId)
    if (!block) return
    const el = containerRef.current?.querySelector(
      `[data-page-index="${block.page_index}"]`,
    )
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [selectedBlockId, blocks])

  useEffect(() => {
    if (selectedPageIndex == null || !numPages) return
    const el = pageRefs.current[selectedPageIndex]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [selectedPageIndex, numPages])

  // Track current visible page via IntersectionObserver
  useEffect(() => {
    if (!numPages) return
    const container = containerRef.current
    if (!container) return

    const observers: IntersectionObserver[] = []
    const visibleRatios = new Map<number, number>()

    pageRefs.current.forEach((el, i) => {
      if (!el) return
      const obs = new IntersectionObserver(
        ([entry]) => {
          visibleRatios.set(i, entry.intersectionRatio)
          // Pick the page with the highest visible ratio
          let best = 0
          let bestRatio = -1
          visibleRatios.forEach((ratio, idx) => {
            if (ratio > bestRatio) { bestRatio = ratio; best = idx }
          })
          const page = best + 1
          setCurrentPage(page)
          setPageInput(String(page))
        },
        { root: container, threshold: Array.from({ length: 21 }, (_, k) => k / 20) },
      )
      obs.observe(el)
      observers.push(obs)
    })

    return () => observers.forEach((o) => o.disconnect())
  }, [numPages])

  const scrollToPage = useCallback((page: number) => {
    const clamped = Math.max(1, Math.min(page, numPages))
    const el = pageRefs.current[clamped - 1]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [numPages])

  const handlePageInputCommit = () => {
    const n = parseInt(pageInput, 10)
    if (!isNaN(n)) scrollToPage(n)
    else setPageInput(String(currentPage))
  }

  if (loadError) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-destructive p-4">
        Failed to load PDF: {loadError}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {numPages > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-background shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            disabled={currentPage <= 1}
            onClick={() => scrollToPage(currentPage - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span>Page</span>
            <Input
              className="h-7 w-12 text-center px-1 text-sm"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onBlur={handlePageInputCommit}
              onKeyDown={(e) => { if (e.key === 'Enter') handlePageInputCommit() }}
            />
            <span>of {numPages}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            disabled={currentPage >= numPages}
            onClick={() => scrollToPage(currentPage + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
      <div ref={containerRef} className="overflow-auto bg-muted/20 p-4 flex-1">
      <Document
        file={pdfFile}
        onLoadSuccess={({ numPages: n }) => setNumPages(n)}
        onLoadError={(err) => setLoadError(err.message)}
        loading={
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            Loading PDF…
          </div>
        }
      >
        {Array.from({ length: numPages }, (_, i) => {
          const pageBlocks = blocks.filter(
            (b) => b.page_index === i && b.bbox != null,
          )
          return (
            <div
              key={i}
              ref={(el) => { pageRefs.current[i] = el }}
              data-page-index={i}
              className="relative mb-4 shadow-sm"
            >
              <Page
                pageNumber={i + 1}
                width={600}
                renderAnnotationLayer={false}
                renderTextLayer={false}
              />
              <svg
                className="absolute inset-0 w-full h-full"
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                style={{ pointerEvents: 'none' }}
              >
                {pageBlocks.map((b) => {
                  const bbox = b.bbox!
                  const isSelected = b.id === selectedBlockId
                  const color = blockColors?.get(b.id) ?? ROLE_COLOR[b.role] ?? DEFAULT_COLOR
                  return (
                    <rect
                      key={b.id}
                      data-testid={`bbox-rect-${b.id}`}
                      x={bbox.x0}
                      y={bbox.y0}
                      width={bbox.x1 - bbox.x0}
                      height={bbox.y1 - bbox.y0}
                      fill={color}
                      fillOpacity={isSelected ? 0.5 : 0.2}
                      stroke={color}
                      strokeOpacity={isSelected ? 1 : 0}
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                      style={{ pointerEvents: 'auto', cursor: 'pointer' }}
                      onClick={() => onBlockSelect(b.id)}
                    />
                  )
                })}
              </svg>
            </div>
          )
        })}
      </Document>
      </div>
    </div>
  )
}
