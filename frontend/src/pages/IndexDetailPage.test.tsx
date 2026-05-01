import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import IndexDetailPage from './IndexDetailPage'

const { mockIndex, mockParsedDocs } = vi.hoisted(() => {
  const mockIndex = {
    id: 'idx-1',
    projectId: 'proj-1',
    name: 'My Index',
    description: null,
    config: {
      sourceRepresentation: 'full_markdown',
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      chunkingStrategy: 'markdown_heading',
      chunkSize: 512,
      chunkOverlap: 50,
      chunkUnit: 'characters',
      splitHeadingLevel: 2,
      maxSectionChars: 4000,
      embeddingProvider: 'openai',
      embeddingModel: 'text-embedding-3-small',
      embeddingDimensions: null,
    },
    stats: null,
    status: 'ready',
    version: 1,
    configDirty: false,
    errorMessage: null,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    documentCount: 1,
    chunkCount: 10,
    documentIds: ['doc-1'],
  }

  const mockParsedDocs = [
    {
      parseRunId: 'pr-1',
      sourceFilename: 'acme-msa.pdf',
      parsedAt: '2026-04-30T09:11:00Z',
      status: 'completed',
      chunksCreated: 10,
    },
  ]

  return { mockIndex, mockParsedDocs }
})

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test' } }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ indexId: 'idx-1' }) }
})

vi.mock('@/hooks/useIndexes', () => ({
  useIndexDetail: () => ({
    index: mockIndex,
    chunks: null,
    isLoading: false,
    error: null,
    fetchIndex: vi.fn().mockResolvedValue(undefined),
    fetchChunks: vi.fn().mockResolvedValue(undefined),
    getChunk: vi.fn(),
  }),
  useIndexes: () => ({
    updateIndex: vi.fn(),
    processIndex: vi.fn(),
  }),
}))

vi.mock('@/api/indexes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/indexes')>()
  return {
    ...actual,
    listIndexParsedDocuments: vi.fn().mockResolvedValue(mockParsedDocs),
    removeIndexParsedDocument: vi.fn().mockResolvedValue(undefined),
    addParsedDocuments: vi.fn().mockResolvedValue(mockIndex),
  }
})

vi.mock('@/lib/parsed-documents', () => ({
  listParsedDocuments: vi.fn().mockResolvedValue([
    {
      id: 'pd-new',
      parseRunId: 'pr-new',
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      sourceDocumentId: 'sd-new',
      sourceFilename: 'vendor.pdf',
      hasFullMarkdown: true,
      blockCount: 5,
      parsedAt: '2026-04-30T10:00:00Z',
    },
  ]),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <IndexDetailPage />
    </MemoryRouter>,
  )
}

describe('IndexDetailPage — Parsed Documents tab', () => {
  it('shows "Parsed Documents" section heading', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/parsed documents/i)).toBeInTheDocument(),
    )
  })

  it('renders the source filename column', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument(),
    )
  })

  it('renders the chunks created column', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('10')).toBeInTheDocument(),
    )
  })
})
