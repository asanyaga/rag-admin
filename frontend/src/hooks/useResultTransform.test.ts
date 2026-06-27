import { it, expect, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import * as api from '@/api/resultTransforms'
import { useResultTransform } from './useResultTransform'

vi.mock('@/api/resultTransforms')

it('populates previewData after preview()', async () => {
  const mockPreview = api.previewTransform as unknown as ReturnType<typeof vi.fn>
  mockPreview.mockResolvedValue({ rows: [{ sku: 'X' }], flags: [] })
  const { result } = renderHook(() => useResultTransform('p1'))
  await act(async () => {
    await result.current.preview({ sourceResultIds: ['r1'], transformType: 'merge_records', config: {} })
  })
  await waitFor(() => expect(result.current.previewData?.rows).toHaveLength(1))
})
