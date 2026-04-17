import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDocuments } from './useDocuments'
import * as documentsApi from '@/api/documents'

vi.mock('@/api/documents')

const mockDocumentListItem = (id: string, status = 'processing') => ({
  id,
  projectId: 'project-1',
  sourceType: 'upload',
  title: id,
  description: null,
  status,
  statusMessage: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
})

const mockDocument = (id: string, status = 'processing') => ({
  ...mockDocumentListItem(id, status),
  sourceIdentifier: 'hash',
  extractedText: null,
  sourceMetadata: {},
  processingMetadata: null,
  createdBy: 'user-1',
})

describe('useDocuments.uploadDocumentsBulk', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue([])
  })

  it('adds successful documents to state and starts polling for processing ones', async () => {
    const bulkResponse = {
      results: [
        { filename: 'doc1.pdf', document: mockDocument('id-1', 'processing'), error: null },
        { filename: 'doc2.pdf', document: null, error: 'File too large' },
      ],
    }
    vi.mocked(documentsApi.bulkUploadDocuments).mockResolvedValue(bulkResponse)
    vi.mocked(documentsApi.getDocument).mockResolvedValue(mockDocument('id-1', 'ready'))

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await result.current.uploadDocumentsBulk({
        projectId: 'project-1',
        files: [new File(['content'], 'doc1.pdf'), new File(['content'], 'doc2.pdf')],
      })
    })

    // Only the successful document should be added to the list
    expect(result.current.documents).toHaveLength(1)
    expect(result.current.documents[0].id).toBe('id-1')
  })

  it('does not add failed documents to state', async () => {
    const bulkResponse = {
      results: [
        { filename: 'bad.pdf', document: null, error: 'Invalid file type' },
      ],
    }
    vi.mocked(documentsApi.bulkUploadDocuments).mockResolvedValue(bulkResponse)

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await result.current.uploadDocumentsBulk({
        projectId: 'project-1',
        files: [new File(['content'], 'bad.pdf')],
      })
    })

    expect(result.current.documents).toHaveLength(0)
  })

  it('throws and sets error on network failure', async () => {
    vi.mocked(documentsApi.bulkUploadDocuments).mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await expect(
        result.current.uploadDocumentsBulk({ projectId: 'project-1', files: [] })
      ).rejects.toThrow('Network error')
    })

    expect(result.current.error).toBe('Network error')
  })
})
