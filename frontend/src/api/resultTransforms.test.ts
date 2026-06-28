import { describe, it, expect, vi, beforeEach } from 'vitest'
import apiClient from './client'
import { previewTransform } from './resultTransforms'

vi.mock('./client')

describe('resultTransforms api', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts preview to the project-scoped endpoint', async () => {
    const mockPost = apiClient.post as unknown as ReturnType<typeof vi.fn>
    mockPost.mockResolvedValue({ data: { rows: [], flags: [] } })
    await previewTransform('p1', {
      sourceResultIds: ['r1'], transformType: 'merge_records', config: {},
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/projects/p1/result-transforms/preview',
      { sourceResultIds: ['r1'], transformType: 'merge_records', config: {} },
    )
  })
})
