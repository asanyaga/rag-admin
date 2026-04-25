import { JsonView, defaultStyles } from 'react-json-view-lite'
import 'react-json-view-lite/dist/index.css'
import { Button } from '@/components/ui/button'
import { Copy, Download } from 'lucide-react'

interface RawPayloadViewerProps {
  payload: Record<string, unknown> | null | undefined
  isLoading?: boolean
  error?: string | null
}

export function RawPayloadViewer({
  payload,
  isLoading = false,
  error = null,
}: RawPayloadViewerProps) {
  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading…</div>
  }
  if (error) {
    return <div className="p-4 text-sm text-destructive">{error}</div>
  }
  if (payload === null) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No raw payload was captured for this run.
      </div>
    )
  }
  if (payload === undefined) {
    return null
  }

  const json = JSON.stringify(payload, null, 2)

  const handleCopy = () => {
    void navigator.clipboard.writeText(json)
  }
  const handleDownload = () => {
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'raw-payload.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b px-3 py-2 gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          Raw parser payload
        </span>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={handleCopy}>
            <Copy className="h-3 w-3 mr-1" /> Copy
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDownload}>
            <Download className="h-3 w-3 mr-1" /> Download
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs">
        <JsonView data={payload} style={defaultStyles} />
      </div>
    </div>
  )
}
