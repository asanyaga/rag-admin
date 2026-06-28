import { useState, useCallback } from 'react'
import { previewTransform, applyTransform, getTransformCatalog } from '@/api/resultTransforms'
import type { TransformPreview, TransformPreviewRequest, TransformCatalogItem } from '@/types/resultTransform'

export function useResultTransform(projectId: string) {
  const [catalog, setCatalog] = useState<TransformCatalogItem[]>([])
  const [previewData, setPreviewData] = useState<TransformPreview | null>(null)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadCatalog = useCallback(async () => setCatalog(await getTransformCatalog()), [])
  const preview = useCallback(async (body: TransformPreviewRequest) => {
    setLoading(true); setError(null)
    try { setPreviewData(await previewTransform(projectId, body)) }
    catch (e) { setError(String(e)) } finally { setLoading(false) }
  }, [projectId])
  const apply = useCallback(
    (body: TransformPreviewRequest & { targetSchemaId?: string }) => applyTransform(projectId, body),
    [projectId])

  return { catalog, loadCatalog, preview, apply, previewData,
           flags: previewData?.flags ?? [], isLoading, error }
}
