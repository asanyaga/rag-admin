import { useMemo } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { Block, ParsedDocumentDetail } from '@/types/cdm'

export interface ParsedDocumentPaneProps {
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading?: boolean
  error?: string | null
}

export function PageBlockList({ blocks }: { blocks: Block[] }) {
  if (blocks.length === 0) {
    return <p className="text-xs text-muted-foreground">No blocks on this page.</p>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b) => {
        const preview = (b.text ?? b.markdown ?? '').slice(0, 140)
        const confidence = b.quality?.confidence
        return (
          <Collapsible key={b.id}>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-2 py-1 hover:bg-muted/50">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {b.role}
                  </Badge>
                  {typeof confidence === 'number' && (
                    <Badge variant="outline" className="text-xs">
                      {confidence.toFixed(2)}
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground truncate flex-1">
                    {preview || <em>empty</em>}
                  </span>
                </div>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="border border-t-0 rounded-b-md px-3 py-2 space-y-2 -mt-px">
              {b.markdown ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                    {b.markdown}
                  </Markdown>
                </div>
              ) : b.text ? (
                <pre className="whitespace-pre-wrap font-mono text-xs">{b.text}</pre>
              ) : (
                <p className="text-xs text-muted-foreground">No text/markdown.</p>
              )}
              <div className="text-xs text-muted-foreground space-y-0.5">
                {b.native_type && <div>native_type: {b.native_type}</div>}
                {b.bbox && (
                  <div>
                    bbox: ({b.bbox.x0.toFixed(3)}, {b.bbox.y0.toFixed(3)}) →
                    ({b.bbox.x1.toFixed(3)}, {b.bbox.y1.toFixed(3)})
                  </div>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}

export function ParsedDocumentPane({
  parsedDocument,
  isLoading = false,
  error = null,
}: ParsedDocumentPaneProps) {
  const blocksByPage = useMemo<Map<number, Block[]>>(() => {
    const map = new Map<number, Block[]>()
    const blocks = parsedDocument?.content?.blocks ?? []
    for (const b of blocks) {
      const arr = map.get(b.page_index) ?? []
      arr.push(b)
      map.set(b.page_index, arr)
    }
    return map
  }, [parsedDocument])

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading…</div>
  }
  if (error) {
    return <div className="p-4 text-sm text-destructive">{error}</div>
  }
  if (!parsedDocument) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No adapted document for this run.
      </div>
    )
  }

  const pages = parsedDocument.content?.pages ?? []
  if (pages.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">No pages.</div>
    )
  }

  return (
    <div className="space-y-3 p-3">
      {pages.map((p) => {
        const blocks = blocksByPage.get(p.index) ?? []
        const confidence = p.quality?.confidence
        return (
          <Collapsible key={p.index} defaultOpen>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-3 py-2 hover:bg-muted/50">
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-medium">Page {p.index + 1}</span>
                  <span className="text-muted-foreground text-xs">
                    {blocks.length} block{blocks.length === 1 ? '' : 's'}
                  </span>
                  {typeof confidence === 'number' && (
                    <Badge variant="outline" className="text-xs ml-auto">
                      confidence {confidence.toFixed(2)}
                    </Badge>
                  )}
                </div>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="border border-t-0 rounded-b-md p-3 -mt-px">
              <PageBlockList blocks={blocks} />
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
