import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import IndexDetailPage from './IndexDetailPage'
import { useIndexDetail, useIndexes } from '@/hooks/useIndexes'

const { mockIndex, mockParsedDocs } = vi.hoisted(() => {
  const mockIndex = {
    id: 'idx-1',
    projectId: 'proj-1',
    name: 'My Index',
    description: null,
    config: {
      sourceRepresentation: 'full_text' as const,
      parser: 'llamaparse',
      parseConfigHash: 'abc123def456',
      chunkingStrategy: 'recursive_character' as const,
      chunkSize: 512,
      chunkOverlap: 50,
      chunkUnit: 'characters' as const,
      splitHeadingLevel: 2,
      maxSectionChars: 10000,
      groupByHeading: true,
      maxBlocksPerChunk: 10,
      blockRoleFilter: null,
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
  useIndexDetail: vi.fn(),
  useIndexes: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(useIndexDetail).mockReturnValue({
    index: mockIndex,
    chunks: null,
    isLoading: false,
    error: null,
    fetchIndex: vi.fn().mockResolvedValue(undefined),
    fetchChunks: vi.fn().mockResolvedValue(undefined),
    getChunk: vi.fn(),
  })
  vi.mocked(useIndexes).mockReturnValue({
    updateIndex: vi.fn(),
    processIndex: vi.fn(),
  })
})

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

import userEvent from '@testing-library/user-event'

describe('IndexDetailPage — Add Documents dialog', () => {
  it('opens a dialog with ParsedDocumentPicker when Add Document is clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Parsed Documents (1)'))

    await user.click(screen.getByRole('button', { name: /add document/i }))

    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'vendor.pdf' })).toBeInTheDocument(),
    )
  })

  it('calls addParsedDocuments with selected IDs on submit', async () => {
    const { addParsedDocuments } = await import('@/api/indexes')
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Parsed Documents (1)'))

    await user.click(screen.getByRole('button', { name: /add document/i }))
    await waitFor(() => screen.getByRole('checkbox', { name: 'vendor.pdf' }))
    await user.click(screen.getByRole('checkbox', { name: 'vendor.pdf' }))
    await user.click(screen.getByRole('button', { name: /^add$/i }))

    expect(addParsedDocuments).toHaveBeenCalledWith(
      'proj-1',
      'idx-1',
      { parsedDocumentIds: ['pr-new'] },
    )
  })
})

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

describe('IndexDetailPage — status gate and config button', () => {
  it('shows the description placeholder when index is ready', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(screen.getByText('Add a description...')).toBeInTheDocument()
  })

  it('does not show the description placeholder when index is processing', async () => {
    vi.mocked(useIndexDetail).mockReturnValue({
      index: { ...mockIndex, status: 'processing' },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(screen.queryByText('Add a description...')).not.toBeInTheDocument()
  })

  it('renders a "Config" button, not "Settings"', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(screen.getByRole('button', { name: /config/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^settings$/i })).not.toBeInTheDocument()
  })

  it('shows a configDirty warning when configDirty is true', async () => {
    vi.mocked(useIndexDetail).mockReturnValue({
      index: { ...mockIndex, configDirty: true },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() =>
      expect(
        screen.getByText(/document set has changed since last index build/i),
      ).toBeInTheDocument(),
    )
  })

  it('does not show configDirty warning when configDirty is false', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(
      screen.queryByText(/document set has changed since last index build/i),
    ).not.toBeInTheDocument()
  })
})
