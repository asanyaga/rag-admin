import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useDocumentProbe } from '@/hooks/useDocumentProbe'
import type { PageProfile } from '@/types/probe'
import { ScanSearch } from 'lucide-react'

interface DocumentProbePanelProps {
  documentId: string
}

function pageTypeBadge(type: PageProfile['page_type']) {
  const variants: Record<PageProfile['page_type'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
    text: 'default',
    scanned: 'destructive',
    mixed: 'secondary',
    empty: 'outline',
  }
  return <Badge variant={variants[type]}>{type}</Badge>
}

function fontHealthBadge(health: PageProfile['font_health']) {
  if (health === 'cid_corrupt') return <Badge variant="destructive">CID corrupt</Badge>
  if (health === 'mixed') return <Badge variant="secondary">mixed</Badge>
  if (health === 'clean') return <Badge variant="default">clean</Badge>
  return <Badge variant="outline">unknown</Badge>
}

export function DocumentProbePanel({ documentId }: DocumentProbePanelProps) {
  const { profile, isLoading, error, runProbe } = useDocumentProbe(documentId)

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium">Document probe</h3>
        <Button variant="outline" size="sm" onClick={runProbe} disabled={isLoading}>
          <ScanSearch className="h-4 w-4 mr-2" />
          {isLoading ? 'Probing…' : profile ? 'Re-probe' : 'Run probe'}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-2">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-3/4" />
        </div>
      )}

      {profile && !isLoading && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            {profile.has_cid_corruption && <Badge variant="destructive">CID corruption</Badge>}
            {profile.has_scanned_pages && <Badge variant="secondary">Scanned pages</Badge>}
            {profile.table_signal && <Badge variant="outline">Table signal</Badge>}
            {!profile.has_text_layer && <Badge variant="destructive">No text layer</Badge>}
          </div>

          <div className="text-xs text-muted-foreground">
            <span className="font-medium">Suggested tools: </span>
            {profile.recommended_tools.join(', ')}
          </div>

          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Page</th>
                  <th className="text-left px-3 py-2 font-medium">Type</th>
                  <th className="text-left px-3 py-2 font-medium">Chars</th>
                  <th className="text-left px-3 py-2 font-medium">Font</th>
                  <th className="text-left px-3 py-2 font-medium">Table?</th>
                  <th className="text-left px-3 py-2 font-medium">Images</th>
                </tr>
              </thead>
              <tbody>
                {profile.pages.map((page) => (
                  <tr key={page.index} className="border-t">
                    <td className="px-3 py-1.5">{page.index + 1}</td>
                    <td className="px-3 py-1.5">{pageTypeBadge(page.page_type)}</td>
                    <td className="px-3 py-1.5">{page.char_count.toLocaleString()}</td>
                    <td className="px-3 py-1.5">{fontHealthBadge(page.font_health)}</td>
                    <td className="px-3 py-1.5">{page.table_signal ? '✓' : '—'}</td>
                    <td className="px-3 py-1.5">{page.image_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-muted-foreground">
            Probed in {profile.duration_ms}ms · {profile.page_count} page{profile.page_count !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </section>
  )
}
