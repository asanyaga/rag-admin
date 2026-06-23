import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function SourceDocumentsPage(): JSX.Element {
  const { sourceDocuments, isLoading, error } = useSourceDocuments()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Source Documents</h1>
        <p className="text-muted-foreground mt-1">
          Tenant-wide document library. Files here persist even when project documents are deleted.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : sourceDocuments.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="font-medium">No source documents yet</p>
          <p className="text-sm mt-1">
            Upload documents via Project Documents to populate this library.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Projects</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sourceDocuments.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="font-medium">{doc.filename ?? '—'}</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {doc.mimeType ?? '—'}
                </TableCell>
                <TableCell>{formatBytes(doc.byteSize)}</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {new Date(doc.createdAt).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{doc.projectCount}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
