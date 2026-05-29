import type { ExtractionResult } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { ChevronDown, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface ExtractionResultViewerProps {
  result: ExtractionResult | null
  isLoading?: boolean
}

function StructuredDataDisplay({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data)

  return (
    <div className="space-y-4">
      {entries.map(([key, value]) => {
        if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
          return <ArrayTable key={key} label={key} items={value as Record<string, unknown>[]} />
        }

        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
          return (
            <Collapsible key={key}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between px-3 py-2 h-auto">
                  <span className="font-medium text-sm">{formatLabel(key)}</span>
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pl-4 border-l-2 border-muted ml-3">
                <StructuredDataDisplay data={value as Record<string, unknown>} />
              </CollapsibleContent>
            </Collapsible>
          )
        }

        return (
          <div key={key} className="flex justify-between items-start py-1.5 px-3 rounded hover:bg-muted/50">
            <span className="text-sm text-muted-foreground">{formatLabel(key)}</span>
            <span className="text-sm text-right max-w-[60%]">{formatValue(value)}</span>
          </div>
        )
      })}
    </div>
  )
}

function ArrayTable({ label, items }: { label: string; items: Record<string, unknown>[] }) {
  if (items.length === 0) return null

  const columns = Object.keys(items[0])

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium px-3">{formatLabel(label)}</h4>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-xs">
                  {formatLabel(col)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell key={col} className="text-sm">
                    {formatValue(item[col])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim()
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function ExtractionResultViewer({
  result,
  isLoading,
}: ExtractionResultViewerProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!result) return null

  const statusColor =
    result.status === 'completed'
      ? 'default'
      : result.status === 'pending'
        ? 'secondary'
        : 'destructive'

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Extraction Result</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={statusColor}>
                {result.status === 'pending' && (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                )}
                {result.status}
              </Badge>
              <Badge variant="outline">{result.extractionMethod}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {result.status === 'pending' && (
            <p className="text-sm text-muted-foreground">Extraction is in progress...</p>
          )}

          {result.status === 'failed' && (
            <div className="space-y-3">
              {result.statusMessage && (
                <p className="text-sm text-destructive">{result.statusMessage}</p>
              )}
              {typeof result.providerResponseRaw?.['raw_content'] === 'string' && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">LLM Response</p>
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto whitespace-pre-wrap max-h-64">
                    {result.providerResponseRaw['raw_content'] as string}
                  </pre>
                </div>
              )}
            </div>
          )}

          {result.status === 'completed' && result.structuredData && (
            <StructuredDataDisplay data={result.structuredData} />
          )}
        </CardContent>
      </Card>

      {result.extractionMetadata && Object.keys(result.extractionMetadata).length > 0 && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-between">
              <span>Extraction Metadata</span>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="pt-4">
                <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(result.extractionMetadata, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}

      {result.providerResponseRaw &&
        Object.keys(result.providerResponseRaw).length > 0 &&
        typeof result.providerResponseRaw['raw_content'] !== 'string' && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-between">
              <span>Provider Response</span>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="pt-4">
                <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(result.providerResponseRaw, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
