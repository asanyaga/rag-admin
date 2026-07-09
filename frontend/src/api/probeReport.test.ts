import { describe, it, expect, vi, beforeEach } from 'vitest'
import { probeDocument } from './probeReport'
import apiClient from './client'

vi.mock('./client', () => ({ default: { post: vi.fn() } }))

describe('probeDocument', () => {
  beforeEach(() => vi.clearAllMocks())
  it('posts document_id + config and returns the report', async () => {
    const report = { document_id: 'd1', pages: [], suggestion: null }
    ;(apiClient.post as any).mockResolvedValue({ data: report })
    const result = await probeDocument('d1')
    expect(apiClient.post).toHaveBeenCalledWith('/probe', { document_id: 'd1', config: null })
    expect(result.document_id).toBe('d1')
  })
})
