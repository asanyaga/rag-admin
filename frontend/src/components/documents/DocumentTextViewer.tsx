import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getDocumentText } from '@/api/documents'

interface DocumentTextViewerProps {
  documentId: string
  documentTitle: string
  onDownload: () => void
}

export function DocumentTextViewer({
  documentId,
  documentTitle,
  onDownload,
}: DocumentTextViewerProps) {
  const [text, setText] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchText = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const extractedText = await getDocumentText(documentId)
        setText(extractedText)
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load text'
        setError(errorMessage)
      } finally {
        setIsLoading(false)
      }
    }

    fetchText()
  }, [documentId])

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-10 w-32" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <svg
            className="mx-auto h-12 w-12 text-red-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <p className="mt-4 text-lg font-medium">Failed to load document</p>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-4">
          <div>
            <h3 className="text-lg font-medium">{documentTitle}</h3>
            <p className="text-sm text-muted-foreground">Extracted Text</p>
          </div>
          <Button onClick={onDownload} variant="outline" size="sm">
            <svg
              className="mr-2 h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
              <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
            </svg>
            Download PDF
          </Button>
        </div>

        {/* Text Content */}
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed bg-muted/30 p-4 rounded-lg max-h-[600px] overflow-y-auto">
            {text}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground border-t pt-4">
          <div>
            <span className="font-medium">Characters:</span>{' '}
            {text?.length.toLocaleString()}
          </div>
          <div>
            <span className="font-medium">Words:</span>{' '}
            {text?.split(/\s+/).length.toLocaleString()}
          </div>
          <div>
            <span className="font-medium">Pages:</span>{' '}
            {(text?.match(/\[Page \d+\]/g) || []).length}
          </div>
        </div>
      </div>
    </Card>
  )
}
